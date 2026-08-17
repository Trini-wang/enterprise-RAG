from pathlib import Path
from importlib import import_module

from fastapi.testclient import TestClient

from app.main import app
from app.services.user_store import UserStore

auth_dependencies = import_module("app.dependencies.auth")
auth_router = import_module("app.routers.auth")
files_router = import_module("app.routers.files")
users_router = import_module("app.routers.users")


def test_registration_login_user_management_and_file_upload(tmp_path: Path, monkeypatch) -> None:
    test_store = UserStore(str(tmp_path / "users.db"))
    monkeypatch.setattr(auth_dependencies, "user_store", test_store)
    monkeypatch.setattr(auth_router, "user_store", test_store)
    monkeypatch.setattr(users_router, "user_store", test_store)
    monkeypatch.setattr(files_router, "UPLOAD_ROOT", tmp_path / "uploads")

    client = TestClient(app)
    admin_response = client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "secure-pass", "full_name": "Admin"},
    )
    assert admin_response.status_code == 201
    assert admin_response.json()["role"] == "admin"
    assert "password" not in admin_response.json()

    user_response = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "secure-pass", "full_name": "User"},
    )
    assert user_response.status_code == 201
    assert user_response.json()["role"] == "user"
    assert client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "secure-pass", "full_name": "Duplicate"},
    ).status_code == 409

    login_response = client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "secure-pass"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/auth/me", headers=headers).status_code == 200
    users_response = client.get("/users", headers=headers)
    assert users_response.status_code == 200
    assert len(users_response.json()) == 2

    user_login = client.post(
        "/auth/login", json={"email": "user@example.com", "password": "secure-pass"}
    )
    user_headers = {"Authorization": f"Bearer {user_login.json()['access_token']}"}
    assert client.get("/users", headers=user_headers).status_code == 403

    upload_response = client.post(
        "/files/upload",
        headers=headers,
        files={"file": ("note.txt", b"hello rag", "text/plain")},
    )
    assert upload_response.status_code == 201
    uploaded = upload_response.json()
    assert uploaded["original_filename"] == "note.txt"
    assert uploaded["size"] == 9

    download_response = client.get(uploaded["download_url"], headers=headers)
    assert download_response.status_code == 200
    assert download_response.content == b"hello rag"
    assert client.delete(uploaded["download_url"], headers=headers).status_code == 204


def test_protected_routes_reject_missing_token() -> None:
    client = TestClient(app)
    assert client.get("/auth/me").status_code == 401
    assert client.get("/users").status_code == 401
    assert client.post("/files/upload", files={"file": ("a.txt", b"a")}).status_code == 401
