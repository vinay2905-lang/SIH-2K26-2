from sqlalchemy import select

from app.models import AuditEvent, UserSession
from tests.conftest import ARANYA_OPERATOR, login


def test_login_sets_httponly_session_cookie(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": ARANYA_OPERATOR, "password": "Demo@12345"}
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "apaar_session=" in cookie
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    body = response.json()
    assert body["user"]["institution"]["code"] == "DEMO-INST-001"
    assert "students.read" in body["user"]["permissions"]
    assert "password" not in response.text.lower().replace("password_", "")


def test_email_is_case_insensitive(client):
    login(client, ARANYA_OPERATOR.upper())


def test_wrong_password_is_generic_and_audited(client, db):
    response = client.post(
        "/api/v1/auth/login", json={"email": ARANYA_OPERATOR, "password": "nope"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Email or password is incorrect"
    unknown = client.post(
        "/api/v1/auth/login", json={"email": "nobody@demo.example", "password": "nope"}
    )
    assert unknown.json()["error"]["message"] == "Email or password is incorrect"
    events = db.scalars(select(AuditEvent).where(AuditEvent.outcome == "failure")).all()
    assert len(events) == 2
    assert all("nope" not in str(e.details) for e in events)


def test_repeated_failures_are_rate_limited(client):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": ARANYA_OPERATOR, "password": "x"})
    response = client.post(
        "/api/v1/auth/login", json={"email": ARANYA_OPERATOR, "password": "Demo@12345"}
    )
    assert response.status_code == 429


def test_protected_routes_require_a_session(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/students").status_code == 401
    assert client.get("/api/v1/students").json()["error"]["code"] == "unauthenticated"


def test_mutations_require_csrf_token(client):
    login(client, ARANYA_OPERATOR)
    token = client.headers.pop("X-CSRF-Token")
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"
    client.headers["X-CSRF-Token"] = "wrong"
    assert client.post("/api/v1/auth/logout").status_code == 403
    client.headers["X-CSRF-Token"] = token
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_logout_revokes_the_server_session(client, db):
    login(client, ARANYA_OPERATOR)
    cookie = client.cookies.get("apaar_session")
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set("apaar_session", cookie)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert db.scalars(select(UserSession)).one().revoked_at is not None


def test_session_token_is_stored_hashed(client, db):
    login(client, ARANYA_OPERATOR)
    cookie = client.cookies.get("apaar_session")
    stored = db.scalars(select(UserSession)).one()
    assert stored.token_hash != cookie and len(stored.token_hash) == 64


def test_security_headers_present(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-request-id"]


def test_public_meta_lists_demo_accounts_without_auth(client):
    body = client.get("/api/v1/meta/public").json()
    assert body["demo_mode"] is True
    assert {a["role"] for a in body["demo_accounts"]} >= {
        "institution_operator",
        "central_reviewer",
        "authorized_verifier",
        "system_admin",
    }
