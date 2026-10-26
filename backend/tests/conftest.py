"""Test harness.

The schema is built with the real Alembic migration and loaded with the synthetic seed once
per session into a template; every test then starts from a fresh copy of that template.
SQLite (default) copies the database file; PostgreSQL (set TEST_DATABASE_URL) clones the
database with CREATE DATABASE ... TEMPLATE.
"""

import os
import shutil
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="apaar-tests-"))
_SQLITE_FILE = _TMP / "test.db"
_SQLITE_TEMPLATE = _TMP / "template.db"
TEST_URL = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_SQLITE_FILE}"
os.environ["DATABASE_URL"] = TEST_URL
os.environ["APP_ENV"] = "test"
os.environ["FRONTEND_DIST_DIR"] = str(_TMP / "no-frontend")

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.v1.auth import login_limiter
from app.db import session as db_session
from app.main import app
from app.seed import DEMO_PASSWORD, seed

BACKEND_DIR = Path(__file__).resolve().parent.parent
IS_SQLITE = TEST_URL.startswith("sqlite")


def _alembic_upgrade() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


def _pg_admin():  # noqa: ANN202
    url = make_url(TEST_URL)
    return url, create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")


def _load_seed() -> None:
    with db_session.SessionLocal() as db:
        seed(db)
        db.commit()
    db_session.engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _template() -> Iterator[None]:
    if IS_SQLITE:
        _alembic_upgrade()
        _load_seed()
        shutil.copyfile(_SQLITE_FILE, _SQLITE_TEMPLATE)
        yield
        shutil.rmtree(_TMP, ignore_errors=True)
        return

    url, admin = _pg_admin()
    template = f"{url.database}_template"
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{template}" WITH (FORCE)'))
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    _alembic_upgrade()
    _load_seed()
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{template}" TEMPLATE "{url.database}"'))
    yield
    db_session.engine.dispose()
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{template}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(autouse=True)
def fresh_db(_template: None) -> Iterator[None]:
    db_session.engine.dispose()
    if IS_SQLITE:
        shutil.copyfile(_SQLITE_TEMPLATE, _SQLITE_FILE)
    else:
        url, admin = _pg_admin()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
            conn.execute(
                text(f'CREATE DATABASE "{url.database}" TEMPLATE "{url.database}_template"')
            )
        admin.dispose()
    login_limiter.reset()
    yield
    db_session.engine.dispose()


@pytest.fixture
def db() -> Iterator[Session]:
    with db_session.SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str = DEMO_PASSWORD) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    client.headers["X-CSRF-Token"] = body["csrf_token"]
    return body


@pytest.fixture
def as_user() -> Iterator[Callable[[str], TestClient]]:
    clients: list[TestClient] = []

    def _make(email: str) -> TestClient:
        test_client = TestClient(app)
        test_client.__enter__()
        clients.append(test_client)
        login(test_client, email)
        return test_client

    yield _make
    for test_client in clients:
        test_client.__exit__(None, None, None)


ARANYA_OPERATOR = "aranya.operator@demo.example"
ARANYA_ADMIN = "aranya.admin@demo.example"
KAVERI_OPERATOR = "kaveri.operator@demo.example"
KAVERI_ADMIN = "kaveri.admin@demo.example"
NARMADA_ADMIN = "narmada.admin@demo.example"
CENTRAL = "central.reviewer@demo.example"
VERIFIER = "verifier@demo.example"
SYSADMIN = "sysadmin@demo.example"
