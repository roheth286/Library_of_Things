"""Library of Things - thin Flask API. All business rules live in PostgreSQL; this layer authenticates, opens a transaction
as the right DB role (SET LOCAL ROLE) and returns JSON."""
import os, sys, contextlib, datetime, decimal, re
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from flask import Flask, jsonify, request, session, send_from_directory
import psycopg2, psycopg2.extras, psycopg2.pool
import jwt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from racelab import run_race, STRATEGIES

DSN = os.environ.get("DATABASE_URL", "dbname=circulend user=circulend password=circulend host=localhost")
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me-32-bytes-minimum-secret-key!")
JWT_SECRET = os.environ.get("JWT_SECRET", app.secret_key)
JWT_ALGORITHM = "HS256"
pool = psycopg2.pool.ThreadedConnectionPool(2, 20, DSN)


class ApiError(Exception):
    def __init__(self, msg, code=400): self.msg, self.code = msg, code


@app.errorhandler(ApiError)
def _api_err(e): return jsonify(error=e.msg), e.code


@app.errorhandler(psycopg2.Error)
def _pg_err(e):
    msg = (e.diag.message_primary if getattr(e, "diag", None) and e.diag.message_primary else str(e)).strip()
    code = {"42501": 403, "23P01": 409, "23505": 409, "40001": 409, "P0002": 409, "23514": 400, "23503": 400}.get(e.pgcode, 400)
    if e.pgcode == "42501": msg = "Not permitted for your role"
    if e.pgcode == "23P01": msg = msg if "not available" in msg else "That unit is already booked for those dates"
    if e.pgcode == "23505": msg = "Conflicts with an existing record: " + msg
    return jsonify(error=msg, pgcode=e.pgcode), code


def _json(o):
    if isinstance(o, (datetime.date, datetime.datetime)): return o.isoformat()
    if isinstance(o, decimal.Decimal): return float(o)
    raise TypeError


app.json.default = _json


@contextlib.contextmanager
def tx(role=None, member_id=None):
    """One transaction per request, executed as circulend_member / circulend_staff with the RLS member id."""
    con = pool.getconn()
    try:
        cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if role:
            cur.execute("SELECT set_config('app.member_id', %s, true)", (str(member_id or ""),))
            cur.execute("SET LOCAL ROLE " + ("circulend_staff" if role in ("staff", "admin") else "circulend_member"))
        yield cur
        con.commit()
    except Exception:
        con.rollback(); raise
    finally:
        pool.putconn(con)


def _create_jwt(user_dict):
    payload = {
        "sub": str(user_dict["member_id"]),
        "member_id": user_dict["member_id"],
        "name": user_dict["name"],
        "role": user_dict["role"],
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_jwt(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def me(required=True, staff=False):
    u = session.get("user")
    if not u:
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            payload = _decode_jwt(auth_hdr[7:].strip())
            if payload:
                u = {"member_id": payload["member_id"], "name": payload["name"], "role": payload["role"]}
    if not u:
        token = request.cookies.get("token")
        if token:
            payload = _decode_jwt(token)
            if payload:
                u = {"member_id": payload["member_id"], "name": payload["name"], "role": payload["role"]}

    if required and not u: raise ApiError("Please sign in", 401)
    if staff and (not u or u["role"] not in ("staff", "admin")): raise ApiError("Staff only", 403)
    return u


def body(*req):
    d = request.get_json(silent=True) or {}
    for k in req:
        if d.get(k) in (None, ""): raise ApiError(f"Missing field: {k}")
    return d


EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

def validate_email_address(email):
    email = (email or "").strip()
    if not email:
        raise ApiError("Email address is required")
    if not EMAIL_REGEX.match(email) or ".." in email:
        raise ApiError("Invalid email address format")
    local_part, _, domain = email.partition("@")
    if not local_part or not domain or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ApiError("Invalid email address format")
    return email.lower()


def validate_password_policy(pw):
    if not pw or len(pw) < 8:
        raise ApiError("Password must be at least 8 characters long")
    if not re.search(r'\d', pw):
        raise ApiError("Password must contain at least one numeric digit (0-9)")
    if not re.search(r'[A-Z]', pw):
        raise ApiError("Password must contain at least one uppercase letter (A-Z)")
    if not re.search(r'[a-z]', pw):
        raise ApiError("Password must contain at least one lowercase letter (a-z)")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', pw):
        raise ApiError("Password must contain at least one special character")


# ───────── auth ─────────
@app.post("/api/register")
def register():
    d = body("name", "email", "password", "confirm_password")
    name = d["name"].strip()
    if not name:
        raise ApiError("Name is required")
    email = validate_email_address(d["email"])
    pw = d["password"]
    cpw = d["confirm_password"]

    if pw != cpw:
        raise ApiError("Passwords do not match")
    validate_password_policy(pw)

    # Public registration strictly forces role to 'member'
    # Any role provided in body is ignored or rejected if attempting admin
    if d.get("role") and d.get("role") not in ("member", "user"):
        raise ApiError("Public registration is only permitted for regular members", 403)

    with tx() as c:
        c.execute("SELECT 1 FROM members WHERE lower(email) = lower(%s)", (email,))
        if c.fetchone():
            raise ApiError("An account with this email address already exists", 409)

        c.execute(
            "INSERT INTO members(name, email, password_hash, role) VALUES (%s, %s, crypt(%s, gen_salt('bf')), 'member') RETURNING member_id, name, email, role",
            (name, email, pw)
        )
        new_user = dict(c.fetchone())

    token = _create_jwt(new_user)
    session["user"] = new_user

    resp = jsonify(
        ok=True,
        message=f"Registration successful! Welcome to Library of Things, {new_user['name']}!",
        user={"member_id": new_user["member_id"], "name": new_user["name"], "role": new_user["role"]},
        token=token
    )
    is_secure = request.is_secure or request.headers.get("X-Forwarded-Proto") == "https"
    resp.set_cookie(
        "token",
        token,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
        max_age=86400,
        path="/"
    )
    return resp, 201


@app.post("/api/login")
def login():
    d = body("email", "password")
    email = (d["email"] or "").strip().lower()
    selected_role = (d.get("role") or "").strip()

    with tx() as c:
        c.execute("SELECT member_id, name, role FROM members WHERE lower(email)=lower(%s) AND active AND password_hash = crypt(%s, password_hash)",
                  (email, d["password"]))
        u = c.fetchone()
    if not u:
        raise ApiError("Wrong e-mail or password", 401)

    u_dict = dict(u)
    # Role validation if role selector provided
    if selected_role:
        expected_role = selected_role.lower()
        # map 'user' / 'member'
        if expected_role in ("user", "member"):
            if u_dict["role"] not in ("member", "user"):
                raise ApiError(f"Account does not match the selected '{selected_role}' role", 403)
        elif expected_role == "admin":
            if u_dict["role"] != "admin":
                raise ApiError("Account does not have administrator privileges", 403)
        elif expected_role == "staff":
            if u_dict["role"] not in ("staff", "admin"):
                raise ApiError("Account does not have staff privileges", 403)
        elif u_dict["role"] != expected_role:
            raise ApiError(f"Account does not match the selected '{selected_role}' role", 403)

    token = _create_jwt(u_dict)
    session["user"] = u_dict

    resp = jsonify(dict(u_dict, token=token))
    # Set HttpOnly cookie
    is_secure = request.is_secure or request.headers.get("X-Forwarded-Proto") == "https"
    resp.set_cookie(
        "token",
        token,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
        max_age=86400,
        path="/"
    )
    return resp


@app.post("/api/logout")
def logout():
    session.clear()
    resp = jsonify(ok=True)
    resp.delete_cookie("token", path="/")
    return resp


@app.get("/api/me")
def whoami():
    return jsonify(me(required=False))


@app.get("/api/demo-accounts")
def demo_accounts():
    with tx() as c:
        c.execute("""(SELECT name,email,role FROM members WHERE role='admin' LIMIT 1) UNION ALL
                     (SELECT name,email,role FROM members WHERE role='staff' ORDER BY member_id LIMIT 1) UNION ALL
                     (SELECT name,email,role FROM members WHERE role='member' ORDER BY member_id LIMIT 3)""")
        return jsonify(c.fetchall())



# ───────── catalogue ─────────
@app.get("/api/categories")
def categories():
    u = me()
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT category_id, name FROM categories ORDER BY name"); return jsonify(c.fetchall())


@app.get("/api/tools")
def tools():
    u = me(); q = "%" + request.args.get("q", "") + "%"; cat = request.args.get("category")
    with tx(u["role"], u["member_id"]) as c:
        c.execute("""SELECT a.*, t.description FROM v_tool_availability a JOIN tools t USING (tool_id)
                     WHERE a.name ILIKE %s AND (%s::text IS NULL OR a.category = %s) ORDER BY a.category, a.name""", (q, cat, cat))
        return jsonify(c.fetchall())


@app.get("/api/tools/<int:tid>/units")
def tool_units(tid):
    u = me()
    with tx(u["role"], u["member_id"]) as c:
        c.execute("""SELECT unit_id, unit_no, serial_no, status, condition_status,
                      (SELECT min(l.due_date) FROM loans l WHERE l.unit_id = tu.unit_id AND l.return_date IS NULL) AS due_back
                     FROM tool_units tu WHERE tool_id=%s ORDER BY unit_no""", (tid,))
        return jsonify(c.fetchall())


@app.get("/api/kits")
def kits():
    u = me()
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT * FROM v_kit_availability ORDER BY name"); return jsonify(c.fetchall())


@app.post("/api/kits/<int:kid>/reserve")
def reserve_kit(kid):
    u = me()
    if u["role"] not in ("member", "user"):
        raise ApiError("Kit reservations are for members only", 403)
    d = body("date", "days")
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT sp_reserve_kit(%s, %s, %s, %s) AS reservations",
                  (kid, u["member_id"], d["date"], int(d["days"])))
        res = c.fetchone()
        return jsonify(ok=True, reservations=res["reservations"])


# ───────── member actions ─────────
@app.post("/api/reserve")
def reserve():
    u = me()
    if u["role"] not in ("member", "user"):
        raise ApiError("Tool reservations are for members only", 403)
    d = body("tool_id", "date", "days")
    member = u["member_id"]
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT * FROM sp_reserve(%s,%s,%s,%s,%s)", (member, d["tool_id"], d.get("unit_id"), d["date"], int(d["days"])))
        return jsonify(c.fetchone())


@app.post("/api/reservations/<int:rid>/cancel")
def cancel(rid):
    u = me()
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT 1 FROM reservations WHERE reservation_id=%s", (rid,))
        if not c.fetchone(): raise ApiError("Reservation not found", 404)     # RLS hides other members' rows
        c.execute("SELECT sp_cancel_reservation(%s)", (rid,)); return jsonify(ok=True)


@app.get("/api/my")
def my():
    u = me()
    if u["role"] not in ("member", "user"):
        raise ApiError("Member account is for members only", 403)
    out = {}
    with tx(u["role"], u["member_id"]) as c:
        mid = u["member_id"]
        c.execute("""SELECT l.loan_id, t.name tool, un.unit_no, l.loan_date, l.due_date, l.return_date, l.status, l.late_fee, d.amount deposit, d.status deposit_status
                     FROM loans l JOIN tool_units un USING (unit_id) JOIN tools t USING (tool_id) LEFT JOIN deposits d USING (loan_id)
                     WHERE l.member_id=%s ORDER BY l.loan_id DESC LIMIT 25""", (mid,)); out["loans"] = c.fetchall()
        c.execute("""SELECT r.reservation_id, t.name tool, un.unit_no, r.reserved_for_date, r.duration_days, r.status, r.source, r.expires_at
                     FROM reservations r JOIN tool_units un USING (unit_id) JOIN tools t USING (tool_id)
                     WHERE r.member_id=%s ORDER BY r.reservation_id DESC LIMIT 15""", (mid,)); out["reservations"] = c.fetchall()
        c.execute("""SELECT w.waitlist_id, t.name tool, w.position, w.status, w.requested_at FROM waitlists w JOIN tools t USING (tool_id)
                     WHERE w.member_id=%s ORDER BY w.waitlist_id DESC LIMIT 10""", (mid,)); out["waitlist"] = c.fetchall()
        c.execute("SELECT notification_id, message, kind, created_at, read FROM notifications WHERE member_id=%s ORDER BY notification_id DESC LIMIT 15", (mid,))
        out["notifications"] = c.fetchall()
    return jsonify(out)


@app.post("/api/notifications/read")
def read_notifs():
    u = me()
    with tx(u["role"], u["member_id"]) as c:
        c.execute("UPDATE notifications SET read = true WHERE member_id=%s", (u["member_id"],)); return jsonify(ok=True)


# ───────── staff ─────────
@app.get("/api/staff/members")
def staff_members():
    u = me(staff=True); q = "%" + request.args.get("q", "") + "%"
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT member_id, name, email, role, active_loans_count, max_loans FROM members WHERE active AND (name ILIKE %s OR email ILIKE %s) ORDER BY name LIMIT 30", (q, q))
        return jsonify(c.fetchall())


@app.get("/api/staff/desk")
def desk():
    u = me(staff=True)
    with tx(u["role"], u["member_id"]) as c:
        c.execute("""SELECT l.loan_id, m.name member, t.name tool, un.unit_no, l.loan_date, l.due_date, l.status,
                            GREATEST(current_date - l.due_date, 0) days_late, d.amount deposit
                     FROM loans l JOIN members m USING (member_id) JOIN tool_units un USING (unit_id) JOIN tools t USING (tool_id)
                     LEFT JOIN deposits d USING (loan_id) WHERE l.return_date IS NULL ORDER BY l.due_date""")
        loans = c.fetchall()
        c.execute("""SELECT r.reservation_id, r.member_id, m.name member, t.name tool, un.unit_no, un.unit_id, r.reserved_for_date, r.duration_days, r.source, r.expires_at
                     FROM reservations r JOIN members m USING (member_id) JOIN tool_units un USING (unit_id) JOIN tools t USING (tool_id)
                     WHERE r.status='Active' ORDER BY r.reserved_for_date""")
        res = c.fetchall()
        c.execute("""SELECT un.unit_id, t.name tool, un.unit_no, un.status, un.condition_status,
                            (SELECT string_agg(dr.severity::text || ': ' || dr.description, '; ' ORDER BY dr.report_id DESC) FROM damage_reports dr WHERE dr.unit_id = un.unit_id) AS notes
                     FROM tool_units un JOIN tools t USING (tool_id) WHERE un.status IN ('Repair') ORDER BY t.name, un.unit_no""")
        repairs = c.fetchall()
        c.execute("""SELECT t.tool_id, t.name, a.available_units FROM tools t JOIN v_tool_availability a USING (tool_id) ORDER BY t.name""")
        tl = c.fetchall()
    return jsonify(loans=loans, reservations=res, repairs=repairs, tools=tl)


@app.post("/api/staff/checkout")
def checkout():
    u = me(staff=True); d = body("unit_id", "member_id", "days")
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT sp_checkout(%s,%s,%s,%s) AS loan_id", (d["unit_id"], d["member_id"], d["days"], d.get("reservation_id")))
        return jsonify(c.fetchone())


@app.post("/api/staff/checkout-kit")
def checkout_kit():
    u = me(staff=True); d = body("kit_id", "member_id", "days")
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT sp_checkout_kit(%s,%s,%s) AS loans", (d["kit_id"], d["member_id"], d["days"])); return jsonify(c.fetchone())


@app.post("/api/staff/checkin")
def checkin():
    u = me(staff=True); d = body("loan_id")
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT unit_id FROM loans WHERE loan_id = %s", (d["loan_id"],))
        ln = c.fetchone()
        u_id = ln["unit_id"] if ln else None

        c.execute("SELECT * FROM sp_checkin(%s, %s::severity_level, %s)", (d["loan_id"], d.get("severity") or None, d.get("notes")))
        r = c.fetchone()
        r["promoted"] = None
        if u_id:
            c.execute("""SELECT m.name, t.name AS tool, un.unit_no, r.reservation_id
                         FROM reservations r JOIN members m USING (member_id)
                         JOIN tool_units un USING (unit_id) JOIN tools t USING (tool_id)
                         WHERE un.unit_id = %s AND r.source = 'waitlist' AND r.status = 'Active'
                         ORDER BY r.reservation_id DESC LIMIT 1""", (u_id,))
            r["promoted"] = c.fetchone()
        return jsonify(r)


@app.post("/api/staff/damage")
def damage():
    u = me(staff=True); d = body("unit_id", "severity", "description")
    with tx(u["role"], u["member_id"]) as c:
        c.execute("INSERT INTO damage_reports(unit_id, description, severity) VALUES (%s,%s,%s::severity_level)", (d["unit_id"], d["description"], d["severity"]))
        c.execute("SELECT status::text, condition_status::text AS condition FROM tool_units WHERE unit_id=%s", (d["unit_id"],)); return jsonify(c.fetchone())


@app.post("/api/staff/repair")
def repair():
    u = me(staff=True); d = body("unit_id")
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT sp_complete_repair(%s)", (d["unit_id"],)); return jsonify(ok=True)


@app.post("/api/staff/deposit/<action>")
def deposit(action):
    u = me(staff=True); d = body("loan_id")
    if action != "release": raise ApiError("Action not allowed", 400)
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT sp_release_deposit(%s) AS r", (d["loan_id"],))
        return jsonify(c.fetchone())


@app.get("/api/staff/waitlists")
def staff_waitlists():
    u = me(staff=True)
    with tx(u["role"], u["member_id"]) as c:
        c.execute("""
            SELECT t.tool_id, t.name AS tool, c.name AS category,
                   t.deposit_amount, t.max_loan_days,
                   count(u.*) AS total_units,
                   count(*) FILTER (WHERE u.status = 'Available') AS available_units,
                   count(*) FILTER (WHERE u.status = 'Loaned') AS loaned_units,
                   count(*) FILTER (WHERE u.status = 'Reserved') AS reserved_units,
                   count(*) FILTER (WHERE u.status = 'Repair') AS repair_units,
                   (SELECT count(*) FROM waitlists w WHERE w.tool_id = t.tool_id AND w.status = 'Waiting') AS waiting_count
            FROM tools t
            JOIN categories c USING (category_id)
            LEFT JOIN tool_units u USING (tool_id)
            GROUP BY t.tool_id, c.name
            ORDER BY waiting_count DESC, t.name ASC
        """)
        tools = c.fetchall()

        c.execute("""
            SELECT l.loan_id, l.unit_id, un.unit_no, un.tool_id, t.name AS tool,
                   m.member_id, m.name AS member, m.email,
                   l.loan_date, l.due_date,
                   (l.due_date < current_date) AS is_overdue,
                   CASE WHEN l.due_date < current_date THEN current_date - l.due_date ELSE 0 END AS days_overdue
            FROM loans l
            JOIN tool_units un USING (unit_id)
            JOIN tools t USING (tool_id)
            JOIN members m USING (member_id)
            WHERE l.return_date IS NULL
            ORDER BY l.due_date ASC
        """)
        active_loans = c.fetchall()

        c.execute("""
            SELECT w.waitlist_id, w.tool_id, t.name AS tool,
                   w.member_id, m.name AS member, m.email,
                   w.position, w.status, w.requested_at,
                   r.reservation_id, r.status AS res_status, r.expires_at AS res_expires_at,
                   un.unit_no AS res_unit_no
            FROM waitlists w
            JOIN tools t USING (tool_id)
            JOIN members m USING (member_id)
            LEFT JOIN LATERAL (
                SELECT r.reservation_id, r.status, r.expires_at, r.unit_id
                FROM reservations r
                WHERE r.member_id = w.member_id AND r.source = 'waitlist'
                ORDER BY r.reservation_id DESC LIMIT 1
            ) r ON w.status = 'Promoted'
            LEFT JOIN tool_units un ON un.unit_id = r.unit_id
            ORDER BY t.name, CASE WHEN w.status = 'Waiting' THEN 0 ELSE 1 END, w.position ASC, w.requested_at ASC
        """)
        entries = c.fetchall()

        c.execute("""
            SELECT w.waitlist_id, t.name AS tool, m.name AS member, m.email,
                   w.requested_at, r.reservation_id, un.unit_no, r.created_at AS promoted_at,
                   r.expires_at, r.status AS res_status
            FROM waitlists w
            JOIN tools t USING (tool_id)
            JOIN members m USING (member_id)
            JOIN reservations r ON r.member_id = w.member_id AND r.source = 'waitlist'
            JOIN tool_units un ON un.unit_id = r.unit_id
            WHERE w.status = 'Promoted'
            ORDER BY r.created_at DESC
            LIMIT 15
        """)
        promotions = c.fetchall()

        return jsonify({
            "tools": tools,
            "active_loans": active_loans,
            "entries": entries,
            "promotions": promotions
        })


@app.post("/api/staff/waitlist/cancel")
def staff_cancel_waitlist():
    u = me(staff=True); d = body("waitlist_id")
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT sp_cancel_waitlist(%s)", (d["waitlist_id"],))
        return jsonify(ok=True, message="Waitlist entry cancelled")


@app.post("/api/staff/waitlist/promote")
def staff_promote_waitlist():
    u = me(staff=True); d = body("tool_id")
    with tx(u["role"], u["member_id"]) as c:
        c.execute("SELECT * FROM sp_promote_waitlist(%s)", (d["tool_id"],))
        res = c.fetchone()
        return jsonify(ok=True, promoted=res)


@app.post("/api/staff/jobs/<job>")
def jobs(job):
    u = me(staff=True)
    fn = {"expire": "sp_expire_reservations", "overdue": "sp_mark_overdue"}.get(job)
    if not fn: raise ApiError("Unknown job", 404)
    with tx(u["role"], u["member_id"]) as c:
        c.execute(f"SELECT {fn}() AS n"); return jsonify(c.fetchone())


# ───────── reports ─────────
@app.get("/api/reports")
def reports():
    u = me(staff=True)
    with tx(u["role"], u["member_id"]) as c:
        out = {}
        for key, sql in {
            "fleet": "SELECT * FROM v_fleet_status ORDER BY category",
            "deposits": "SELECT * FROM v_deposit_holds ORDER BY loan_id DESC LIMIT 40",
            "waitlist": "SELECT * FROM v_waitlist_by_tool ORDER BY waiting DESC",
            "duration": "SELECT * FROM v_loan_duration_by_category ORDER BY avg_days_kept DESC",
            "overdue": "SELECT * FROM v_overdue_loans ORDER BY days_overdue DESC",
            "utilisation": "SELECT * FROM v_tool_utilisation LIMIT 8",
            "audit": "SELECT audit_id, table_name, row_id, action, changed_at, db_user FROM audit_log ORDER BY audit_id DESC LIMIT 12",
        }.items():
            c.execute(sql); out[key] = c.fetchall()
        c.execute("""SELECT (SELECT count(*) FROM tool_units) units, (SELECT count(*) FROM members WHERE role='member') members,
                            (SELECT count(*) FROM loans) loans,
                            (SELECT coalesce(sum(amount),0) FROM deposits WHERE status='Held') held,
                            (SELECT coalesce(sum(amount),0) FROM deposits WHERE status='Released') released""")
        out["totals"] = c.fetchone()
        return jsonify(out)


# ───────── concurrency lab ─────────
@app.get("/api/lab/strategies")
def lab_strategies(): me(staff=True); return jsonify(STRATEGIES)


@app.post("/api/lab/run")
def lab_run():
    me(staff=True); d = body("strategy")
    return jsonify(run_race(DSN, d["strategy"], int(d.get("contenders", 2))))


@app.post("/api/admin/reset-demo")
def reset_demo():
    u = me()
    if u["role"] != "admin": raise ApiError("Admin only", 403)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "db"))
    import seed; seed.main(DSN); return jsonify(ok=True)


@app.get("/")
def index(): return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), threaded=True)
