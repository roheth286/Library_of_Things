import pytest
import psycopg2
from conftest import DSN, FIXTURE_SQL
import app as circulend_app


@pytest.fixture()
def client():
    old_pool = circulend_app.pool
    circulend_app.pool = psycopg2.pool.ThreadedConnectionPool(1, 10, DSN)

    # Initialize fixture data
    c = psycopg2.connect(DSN)
    c.autocommit = True
    c.cursor().execute(FIXTURE_SQL)
    c.close()

    circulend_app.app.config["TESTING"] = True
    with circulend_app.app.test_client() as cl:
        yield cl

    circulend_app.pool.closeall()
    circulend_app.pool = old_pool


def test_registration_auto_authenticates_and_navigates(client):
    """User registers and is automatically authenticated with session and JWT cookie."""
    res = client.post("/api/register", json={
        "name": "Auto Login User",
        "email": "autologin@example.in",
        "password": "SecurePassword1!",
        "confirm_password": "SecurePassword1!",
        "role": "member"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["ok"] is True
    assert "Registration successful" in data["message"]
    assert "token" in data
    assert data["user"]["name"] == "Auto Login User"

    # Verify cookie was set
    cookie = res.headers.get("Set-Cookie")
    assert cookie is not None
    assert "token=" in cookie

    # User can immediately access member area without separate login
    res_my = client.get("/api/my")
    assert res_my.status_code == 200
    my_data = res_my.get_json()
    assert "loans" in my_data
    assert "reservations" in my_data


def test_member_kit_reservation_success(client):
    """Available kit can be reserved atomically by a member."""
    # Login as member Alice
    login_res = client.post("/api/login", json={"email": "alice@t.in", "password": "pw"})
    assert login_res.status_code == 200

    # Kit 1 (Camp Kit) requires tool 3 (Tent) and tool 4 (Stove). In fixture, both are available.
    res = client.post("/api/kits/1/reserve", json={
        "date": "2026-10-26",
        "days": 3
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert len(data["reservations"]) == 2

    # Verify reservations exist in DB
    c = psycopg2.connect(DSN)
    cur = c.cursor()
    cur.execute("SELECT reservation_id, source, status FROM reservations WHERE reservation_id = ANY(%s)", (data["reservations"],))
    rows = cur.fetchall()
    c.close()
    assert len(rows) == 2
    for r in rows:
        assert r[1] == "kit"
        assert r[2] == "Active"

    # Check that reservations appear in member's account
    my_res = client.get("/api/my")
    assert my_res.status_code == 200
    my_reservations = my_res.get_json()["reservations"]
    res_ids = [r["reservation_id"] for r in my_reservations]
    assert data["reservations"][0] in res_ids
    assert data["reservations"][1] in res_ids


def test_member_kit_reservation_blocked_no_partial(client):
    """Unavailable kit cannot be reserved and no partial reservations are created."""
    # Login as member Bob
    client.post("/api/login", json={"email": "bob@t.in", "password": "pw"})

    # Check out Stove (tool 4, unit 7) so Camp Kit becomes unavailable
    c = psycopg2.connect(DSN)
    cur = c.cursor()
    cur.execute("SELECT sp_checkout(7, 1, 3)")  # Staff checks out stove to staff
    c.commit()
    c.close()

    # Attempt to reserve Kit 1
    res = client.post("/api/kits/1/reserve", json={
        "date": "2026-10-26",
        "days": 3
    })
    assert res.status_code == 409 or res.status_code == 400
    err_msg = res.get_json()["error"]
    assert "unavailable" in err_msg.lower() or "not available" in err_msg.lower()

    # Verify no reservations were created for Bob
    c = psycopg2.connect(DSN)
    cur = c.cursor()
    cur.execute("SELECT count(*) FROM reservations WHERE member_id = 3 AND status = 'Active'")
    count = cur.fetchone()[0]
    c.close()
    assert count == 0


def test_role_authorization_boundaries(client):
    """Administrators cannot access member-only endpoints; members cannot access staff endpoints."""
    # 1. Login as admin
    login_admin = client.post("/api/login", json={"email": "admin@t.in", "password": "pw", "role": "admin"})
    assert login_admin.status_code == 200

    # Admin should NOT be able to access member-only endpoint /api/my
    res_my = client.get("/api/my")
    assert res_my.status_code == 403
    assert "member" in res_my.get_json()["error"].lower()

    # Admin should NOT be able to call member reservation endpoint /api/reserve
    res_res = client.post("/api/reserve", json={"tool_id": 1, "date": "2026-10-26", "days": 3})
    assert res_res.status_code == 403

    # Admin CAN access staff endpoints
    res_desk = client.get("/api/staff/desk")
    assert res_desk.status_code == 200

    # 2. Login as regular member
    client.post("/api/login", json={"email": "alice@t.in", "password": "pw", "role": "member"})

    # Member CAN access /api/my
    assert client.get("/api/my").status_code == 200

    # Member CANNOT access staff endpoints
    assert client.get("/api/staff/desk").status_code == 403
    assert client.get("/api/reports").status_code == 403
    assert client.get("/api/staff/waitlists").status_code == 403


def test_deposit_release_guardrails(client):
    """Deposits cannot be released before return or before hold period expires."""
    # Login as admin / staff
    login_admin = client.post("/api/login", json={"email": "admin@t.in", "password": "pw", "role": "admin"})
    assert login_admin.status_code == 200

    # Create a loan for Alice with deposit (unit 1, member 2)
    c = psycopg2.connect(DSN)
    cur = c.cursor()
    cur.execute("SELECT sp_checkout(1, 2, 3)")
    loan_id = cur.fetchone()[0]
    c.commit()
    c.close()

    # 1. Attempt to release deposit while item is NOT returned
    res = client.post("/api/staff/deposit/release", json={"loan_id": loan_id})
    assert res.status_code == 400
    assert "not yet returned" in res.get_json()["error"]

    # 2. Return the loan (return window opens for 24h)
    c = psycopg2.connect(DSN)
    cur = c.cursor()
    cur.execute("SELECT sp_checkin(%s)", (loan_id,))
    c.commit()
    c.close()

    # 3. Attempt to release deposit while hold window is still open
    res_early = client.post("/api/staff/deposit/release", json={"loan_id": loan_id})
    assert res_early.status_code == 400
    assert "return window open" in res_early.get_json()["error"]

    # 4. Simulate hold window elapsed by backdating both loan_date and return_date
    c = psycopg2.connect(DSN)
    cur = c.cursor()
    cur.execute("UPDATE loans SET loan_date = current_date - 5, return_date = current_date - 2 WHERE loan_id = %s", (loan_id,))
    c.commit()
    c.close()

    # 5. Now release deposit -> should succeed
    res_ok = client.post("/api/staff/deposit/release", json={"loan_id": loan_id})
    assert res_ok.status_code == 200

    # Verify status in database
    c = psycopg2.connect(DSN)
    cur = c.cursor()
    cur.execute("SELECT status FROM deposits WHERE loan_id = %s", (loan_id,))
    status = cur.fetchone()[0]
    c.close()
    assert status == "Released"


def test_deposit_accounting_and_duplicate_release(client):
    """Releasing twice is idempotent; dashboard totals update; damage prevents release; forfeit is rejected."""
    # Login as staff/admin
    client.post("/api/login", json={"email": "admin@t.in", "password": "pw", "role": "admin"})

    c = psycopg2.connect(DSN)
    cur = c.cursor()
    # Checkout Drill unit 1 (deposit ₹1500) to Alice
    cur.execute("SELECT sp_checkout(1, 2, 3)")
    lid = cur.fetchone()[0]
    c.commit()

    # Check dashboard before return
    rep1 = client.get("/api/reports").get_json()
    held_before = rep1["totals"]["held"]
    rel_before = rep1["totals"]["released"]

    # Return loan with clean condition, backdate to clear 24h window
    cur.execute("SELECT sp_checkin(%s)", (lid,))
    cur.execute("UPDATE loans SET loan_date = current_date - 5, return_date = current_date - 2 WHERE loan_id = %s", (lid,))
    c.commit()

    # Forfeit action must be rejected with 400
    res_forfeit = client.post("/api/staff/deposit/forfeit", json={"loan_id": lid})
    assert res_forfeit.status_code == 400
    assert "Action not allowed" in res_forfeit.get_json()["error"]

    # Release deposit
    res_rel = client.post("/api/staff/deposit/release", json={"loan_id": lid})
    assert res_rel.status_code == 200

    # Release second time (idempotent, does not error or subtract twice)
    res_rel2 = client.post("/api/staff/deposit/release", json={"loan_id": lid})
    assert res_rel2.status_code == 200
    assert "already released" in res_rel2.get_json()["r"]

    # Dashboard totals check
    rep2 = client.get("/api/reports").get_json()
    held_after = rep2["totals"]["held"]
    rel_after = rep2["totals"]["released"]
    assert held_after == held_before - 1500
    assert rel_after == rel_before + 1500

    # Test damage hold prevents deposit release
    cur.execute("SELECT sp_checkout(2, 2, 3)")
    lid_dmg = cur.fetchone()[0]
    cur.execute("SELECT sp_checkin(%s, 'Major'::severity_level, 'Broken motor')", (lid_dmg,))
    cur.execute("UPDATE loans SET loan_date = current_date - 5, return_date = current_date - 2 WHERE loan_id = %s", (lid_dmg,))
    c.commit()
    c.close()

    res_dmg = client.post("/api/staff/deposit/release", json={"loan_id": lid_dmg})
    assert res_dmg.status_code == 400
    assert "damage recorded" in res_dmg.get_json()["error"]


def test_waitlist_admin_lifecycle_and_promotion(client):
    """Admin can inspect waitlists, FIFO ordering, returns cascade, damaged return blocks cascade, and cancel works."""
    # Login as admin
    client.post("/api/login", json={"email": "admin@t.in", "password": "pw", "role": "admin"})

    c = psycopg2.connect(DSN)
    cur = c.cursor()
    # Tool 2 (Washer, 1 unit). Check it out to Bob
    cur.execute("SELECT sp_checkout(4, 3, 3)")
    lid = cur.fetchone()[0]
    c.commit()

    # Alice and Cara join waitlist for Washer (Tool 2)
    cur.execute("SELECT * FROM sp_reserve(2, 2)") # Alice (member 2)
    cur.execute("SELECT * FROM sp_reserve(4, 2)") # Cara (member 4)
    c.commit()

    # Admin checks waitlist API
    wl_res = client.get("/api/staff/waitlists")
    assert wl_res.status_code == 200
    wl_data = wl_res.get_json()

    washer_tool = next(t for t in wl_data["tools"] if t["tool_id"] == 2)
    assert washer_tool["waiting_count"] == 2
    assert washer_tool["loaned_units"] == 1

    # Check active loans info includes borrower Bob and due date
    active_washer_loan = next(l for l in wl_data["active_loans"] if l["tool_id"] == 2)
    assert active_washer_loan["member"] == "Bob"
    assert active_washer_loan["due_date"] is not None

    # Check FIFO queue order: Alice is #1, Cara is #2
    washer_entries = [e for e in wl_data["entries"] if e["tool_id"] == 2 and e["status"] == "Waiting"]
    assert len(washer_entries) == 2
    assert washer_entries[0]["member"] == "Alice" and washer_entries[0]["position"] == 1
    assert washer_entries[1]["member"] == "Cara" and washer_entries[1]["position"] == 2

    # Normal return of Washer: Bob returns loan
    ret_res = client.post("/api/staff/checkin", json={"loan_id": lid})
    assert ret_res.status_code == 200
    ret_data = ret_res.get_json()
    assert ret_data["promoted"] is not None
    assert ret_data["promoted"]["name"] == "Alice"

    # Verify Alice has active reservation for unit 4
    cur.execute("SELECT status, source FROM reservations WHERE member_id = 2 AND unit_id = 4 AND status = 'Active'")
    res_row = cur.fetchone()
    assert res_row is not None and res_row[1] == "waitlist"

    # Verify Cara shifted from #2 to #1
    cur.execute("SELECT position FROM waitlists WHERE member_id = 4 AND tool_id = 2 AND status = 'Waiting'")
    pos_cara = cur.fetchone()[0]
    assert pos_cara == 1

    # Cara cancels her waitlist entry via admin API
    cur.execute("SELECT waitlist_id FROM waitlists WHERE member_id = 4 AND tool_id = 2 AND status = 'Waiting'")
    wid = cur.fetchone()[0]
    c.close()

    cancel_res = client.post("/api/staff/waitlist/cancel", json={"waitlist_id": wid})
    assert cancel_res.status_code == 200

    c = psycopg2.connect(DSN)
    cur = c.cursor()
    cur.execute("SELECT status, position FROM waitlists WHERE waitlist_id = %s", (wid,))
    row_c = cur.fetchone()
    assert row_c[0] == "Cancelled" and row_c[1] is None
    c.close()


def test_loan_limit_exceeding_four_items(client):
    """Member can borrow more than 4 items when inventory permits; low-limit member is still bounded."""
    client.post("/api/login", json={"email": "alice@t.in", "password": "pw"})

    c = psycopg2.connect(DSN)
    cur = c.cursor()

    # Alice borrows 3 units of Drill (units 1, 2, 3), 1 unit of Tent (unit 5), and 1 unit of Tent (unit 6) -> 5 loans!
    cur.execute("SELECT sp_checkout(1, 2, 3)")
    cur.execute("SELECT sp_checkout(2, 2, 3)")
    cur.execute("SELECT sp_checkout(3, 2, 3)")
    cur.execute("SELECT sp_checkout(5, 2, 3)")
    c.commit()

    # Check Alice active loans count is 4
    cur.execute("SELECT active_loans_count FROM members WHERE member_id = 2")
    assert cur.fetchone()[0] == 4

    # 5th simultaneous loan (exceeding 4 items) -> Must succeed!
    cur.execute("SELECT sp_checkout(6, 2, 3)")
    c.commit()

    cur.execute("SELECT active_loans_count FROM members WHERE member_id = 2")
    assert cur.fetchone()[0] == 5

    # Return Alice's loans so units become available
    cur.execute("UPDATE loans SET return_date = current_date, status = 'Returned' WHERE member_id = 2 AND return_date IS NULL")
    cur.execute("UPDATE tool_units SET status = 'Available' WHERE status = 'Loaned'")
    cur.execute("UPDATE members SET active_loans_count = 0 WHERE member_id = 2")
    c.commit()

    # Dan (member 5) has max_loans = 2 -> 3rd loan must still be rejected by trigger
    cur.execute("SELECT sp_checkout(1, 5, 3)")
    cur.execute("SELECT sp_checkout(2, 5, 3)")
    c.commit()

    with pytest.raises(Exception) as exc_info:
        cur.execute("SELECT sp_checkout(3, 5, 3)")
    assert "Loan limit reached" in str(exc_info.value)

    c.close()


def test_frontend_ui_contains_fixes(client):
    """Verify HTML UI contains updated design, interactive kits, deposit columns, waitlist admin, and no forfeit button."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Kit interactivity
    assert "reserveKitDlg" in html
    assert "Reserve kit" in html
    assert "Currently unavailable because" in html
    assert "v_kit_availability" not in html
    assert "components free" not in html

    # Deposit management fixes
    assert ">Forfeit<" not in html
    assert "sp_forfeit" not in html
    assert "Not Returned" in html
    assert "Expected return date" in html
    assert "Actual return date" in html
    assert "Ready to release" in html
    assert "Release Deposit" in html

    # Waitlist management admin tab
    assert "Waitlist management" in html
    assert "loadWaitlist" in html
    assert "Equipment Waitlist Administration" in html
    assert "Borrowing & Return Lifecycle" in html

    # Admin navigation simplification
    assert "user.role==='admin'" in html
