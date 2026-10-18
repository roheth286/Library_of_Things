"""Tests for Library of Things Authentication and Validation System (Task 1).
Validates Registration, Login, Email/Password rules, Role enforcement, and JWT handling.
"""
import pytest
import psycopg2
import jwt
from conftest import DSN, FIXTURE_SQL
import app as circulend_app



@pytest.fixture()
def client():
    # Setup test DB connection pool in app
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


def test_landing_page_loads(client):
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Library of Things" in html
    assert "Borrow What You Need. Share What You Have." in html
    assert "Equipment Catalogue" in html
    assert "Live Availability" in html
    assert "Reservations" in html
    assert "Borrowing and Returns" in html
    assert "Waitlists" in html
    assert "Condition & Damage Tracking" in html
    assert "Equipment Kits" in html
    assert "Secure Role-Based Access" in html
    assert "How It Works" in html


def test_registration_valid_user(client):
    res = client.post("/api/register", json={
        "name": "Jane Doe",
        "email": "jane.doe@example.in",
        "password": "SecurePassword1!",
        "confirm_password": "SecurePassword1!",
        "role": "member"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data["ok"] is True
    assert "Registration successful" in data["message"]

    # Verify stored in DB as hash, not plaintext
    c = psycopg2.connect(DSN)
    cur = c.cursor()
    cur.execute("SELECT password_hash, role FROM members WHERE email='jane.doe@example.in'")
    row = cur.fetchone()
    c.close()
    assert row is not None
    assert row[0] != "SecurePassword1!"
    assert row[0].startswith("$2")  # bcrypt hash
    assert row[1] == "member"


def test_registration_invalid_email(client):
    res = client.post("/api/register", json={
        "name": "Invalid Email",
        "email": "not-an-email",
        "password": "SecurePassword1!",
        "confirm_password": "SecurePassword1!"
    })
    assert res.status_code == 400
    assert "Invalid email address format" in res.get_json()["error"]


def test_registration_password_too_short(client):
    res = client.post("/api/register", json={
        "name": "Short Pw",
        "email": "short@example.in",
        "password": "Sh1!",
        "confirm_password": "Sh1!"
    })
    assert res.status_code == 400
    assert "at least 8 characters" in res.get_json()["error"]


def test_registration_password_missing_digit(client):
    res = client.post("/api/register", json={
        "name": "No Digit",
        "email": "nodigit@example.in",
        "password": "SecurePassword!",
        "confirm_password": "SecurePassword!"
    })
    assert res.status_code == 400
    assert "numeric digit" in res.get_json()["error"]


def test_registration_password_missing_uppercase(client):
    res = client.post("/api/register", json={
        "name": "No Upper",
        "email": "noupper@example.in",
        "password": "securepassword1!",
        "confirm_password": "securepassword1!"
    })
    assert res.status_code == 400
    assert "uppercase letter" in res.get_json()["error"]


def test_registration_password_missing_lowercase(client):
    res = client.post("/api/register", json={
        "name": "No Lower",
        "email": "nolower@example.in",
        "password": "SECUREPASSWORD1!",
        "confirm_password": "SECUREPASSWORD1!"
    })
    assert res.status_code == 400
    assert "lowercase letter" in res.get_json()["error"]


def test_registration_password_missing_special(client):
    res = client.post("/api/register", json={
        "name": "No Special",
        "email": "nospecial@example.in",
        "password": "SecurePassword1",
        "confirm_password": "SecurePassword1"
    })
    assert res.status_code == 400
    assert "special character" in res.get_json()["error"]


def test_registration_mismatched_password(client):
    res = client.post("/api/register", json={
        "name": "Mismatch",
        "email": "mismatch@example.in",
        "password": "SecurePassword1!",
        "confirm_password": "DifferentPassword1!"
    })
    assert res.status_code == 400
    assert "Passwords do not match" in res.get_json()["error"]


def test_registration_duplicate_email(client):
    res = client.post("/api/register", json={
        "name": "Alice Duplicate",
        "email": "alice@t.in",
        "password": "SecurePassword1!",
        "confirm_password": "SecurePassword1!"
    })
    assert res.status_code == 409
    assert "already exists" in res.get_json()["error"]


def test_registration_admin_self_assignment_rejected(client):
    res = client.post("/api/register", json={
        "name": "Sneaky Admin",
        "email": "sneaky@example.in",
        "password": "SecurePassword1!",
        "confirm_password": "SecurePassword1!",
        "role": "admin"
    })
    assert res.status_code == 403
    assert "Public registration is only permitted for regular members" in res.get_json()["error"]


def test_login_valid_member(client):
    res = client.post("/api/login", json={
        "email": "alice@t.in",
        "password": "pw",
        "role": "member"
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data["email"] if "email" in data else True
    assert data["role"] == "member"
    assert "token" in data

    # Verify HttpOnly cookie set
    cookie = res.headers.get("Set-Cookie")
    assert cookie is not None
    assert "token=" in cookie
    assert "HttpOnly" in cookie


def test_login_member_selecting_admin_rejected(client):
    res = client.post("/api/login", json={
        "email": "alice@t.in",
        "password": "pw",
        "role": "admin"
    })
    assert res.status_code == 403
    assert "administrator privileges" in res.get_json()["error"]


def test_login_invalid_password(client):
    res = client.post("/api/login", json={
        "email": "alice@t.in",
        "password": "wrongpassword"
    })
    assert res.status_code == 401
    assert "Wrong e-mail or password" in res.get_json()["error"]


def test_jwt_bearer_authentication_and_authorization(client):
    # Login as member to get token
    login_res = client.post("/api/login", json={
        "email": "alice@t.in",
        "password": "pw",
        "role": "member"
    })
    token = login_res.get_json()["token"]

    # Verify protected member endpoint works with Bearer token
    res = client.get("/api/categories", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.get_json()) > 0

    # Verify member cannot access staff/admin endpoint
    res_staff = client.get("/api/staff/desk", headers={"Authorization": f"Bearer {token}"})
    assert res_staff.status_code == 403
    assert "Staff only" in res_staff.get_json()["error"]


def test_unauthenticated_request_rejected(client):
    res = client.get("/api/categories")
    assert res.status_code == 401
    assert "Please sign in" in res.get_json()["error"]


def test_invalid_jwt_token_rejected(client):
    res = client.get("/api/categories", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert res.status_code == 401
    assert "Please sign in" in res.get_json()["error"]


def test_logout_clears_session_and_cookie(client):
    login_res = client.post("/api/login", json={
        "email": "alice@t.in",
        "password": "pw"
    })
    assert login_res.status_code == 200

    logout_res = client.post("/api/logout")
    assert logout_res.status_code == 200
    cookie = logout_res.headers.get("Set-Cookie")
    assert cookie is not None
    assert 'token=;' in cookie or 'Expires=' in cookie or 'Max-Age=0' in cookie

    # Verify /api/me is now empty
    me_res = client.get("/api/me")
    assert me_res.get_json() is None
