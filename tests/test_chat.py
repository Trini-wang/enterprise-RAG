import os
from importlib import import_module
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.chat_service import ChatService
from app.services.chat_store import ChatStore
from app.services.document_store import DocumentStore
from app.services.llm_provider import CompletionResult
from app.services.user_store import UserStore

auth_dependencies = import_module("app.dependencies.auth")
auth_router = import_module("app.routers.auth")
users_router = import_module("app.routers.users")
chat_router = import_module("app.routers.chat")
models_router = import_module("app.routers.ai_models")
prompts_router = import_module("app.routers.prompts")
conversations_router = import_module("app.routers.conversations")
chat_service_module = import_module("app.services.chat_service")
docs_router = import_module("app.routers.docs")


class FakeProvider:
    calls: list[list[dict[str, str]]] = []

    async def complete(self, messages, temperature, max_tokens):
        self.calls.append(messages)
        if "生成一个4到12个汉字" in messages[0]["content"]:
            return CompletionResult(content="员工年假咨询", input_tokens=20, output_tokens=6)
        has_knowledge = "以下是与问题相关的企业知识" in messages[-1]["content"]
        return CompletionResult(
            content="根据员工手册，年假为五天。[1]" if has_knowledge else "当然可以，我们继续聊。",
            input_tokens=100,
            output_tokens=20,
        )

    async def stream(self, messages, temperature, max_tokens):
        yield {"type": "delta", "content": "流式"}
        yield {"type": "delta", "content": "回答"}
        yield {"type": "usage", "input_tokens": 30, "output_tokens": 4}


def setup_stores(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MODEL_CONFIG_SECRET", "test-model-config-secret")
    database_path = str(tmp_path / "chat.db")
    users = UserStore(database_path)
    chats = ChatStore(database_path)
    documents = DocumentStore()
    for module in (auth_dependencies, auth_router, users_router):
        monkeypatch.setattr(module, "user_store", users)
    for module in (models_router, prompts_router, conversations_router):
        monkeypatch.setattr(module, "chat_store", chats)
    monkeypatch.setattr(chat_router, "chat_store", chats)
    monkeypatch.setattr(chat_router, "chat_service", ChatService(chats, documents))
    monkeypatch.setattr(docs_router, "store", documents)
    monkeypatch.setattr(chat_service_module, "create_provider", lambda provider, model: FakeProvider())
    monkeypatch.setattr(chat_router, "create_provider", lambda provider, model: FakeProvider())
    monkeypatch.setenv("TEST_AI_KEY", "test-secret")
    return chats


def register_and_login(client: TestClient, email: str, name: str) -> dict[str, str]:
    response = client.post("/auth/register", json={"email": email, "password": "secure-pass", "full_name": name})
    assert response.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": "secure-pass"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_chat_uses_knowledge_then_falls_back_to_general_ai(tmp_path: Path, monkeypatch) -> None:
    setup_stores(tmp_path, monkeypatch)
    FakeProvider.calls.clear()
    client = TestClient(app)
    admin_headers = register_and_login(client, "admin-chat@example.com", "Admin")

    provider = client.post("/admin/model-providers", headers=admin_headers, json={
        "name": "Test AI", "base_url": "https://example.invalid/v1", "api_key_env": "TEST_AI_KEY"
    })
    assert provider.status_code == 201
    model = client.post(f"/admin/model-providers/{provider.json()['id']}/models", headers=admin_headers, json={
        "model_key": "test-model", "name": "Test Model", "is_default": True
    })
    assert model.status_code == 201

    assert client.post("/docs/upload", headers=admin_headers, json={
        "name": "员工手册", "content": "公司员工每年享有五天带薪年假。"
    }).status_code == 200

    catalog = client.get("/ai/models", headers=admin_headers).json()
    assert catalog["providers"][0]["models"][0]["name"] == "Test Model"
    prompt_id = client.get("/prompts", headers=admin_headers).json()[0]["id"]
    common = {"provider_id": provider.json()["id"], "model_id": model.json()["id"], "prompt_id": prompt_id}

    first = client.post("/chat/completions", headers=admin_headers, json={
        **common, "message": "员工每年有几天年假？"
    })
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["message"]["knowledge"]["used"] is True
    assert first_body["message"]["knowledge"]["citations"][0]["document_name"] == "员工手册"

    second = client.post("/chat/completions", headers=admin_headers, json={
        **common, "conversation_id": first_body["conversation_id"], "message": "给我讲一个太空笑话"
    })
    assert second.status_code == 200, second.text
    assert second.json()["message"]["knowledge"]["used"] is False
    assert second.json()["message"]["content"] == "当然可以，我们继续聊。"
    detail = client.get(f"/conversations/{first_body['conversation_id']}", headers=admin_headers)
    assert [item["role"] for item in detail.json()["messages"]] == ["user", "assistant", "user", "assistant"]
    assert detail.json()["title"] == "员工年假咨询"
    assert len(FakeProvider.calls[2]) > 2  # system + previous conversation + current question

    streamed = client.post("/chat/completions/stream", headers=admin_headers, json={
        **common, "message": "你好"
    })
    assert streamed.status_code == 200
    assert "event: retrieval.completed" in streamed.text
    assert "event: message.delta" in streamed.text
    assert "流式" in streamed.text and "event: message.completed" in streamed.text


def test_conversations_are_isolated_and_admin_config_is_protected(tmp_path: Path, monkeypatch) -> None:
    chats = setup_stores(tmp_path, monkeypatch)
    client = TestClient(app)
    admin_headers = register_and_login(client, "admin-isolation@example.com", "Admin")
    user_headers = register_and_login(client, "user-isolation@example.com", "User")
    admin_id = client.get("/auth/me", headers=admin_headers).json()["id"]
    conversation = chats.create_conversation(admin_id, {})

    assert client.get(f"/conversations/{conversation.id}", headers=user_headers).status_code == 404
    assert client.get("/admin/model-providers", headers=user_headers).status_code == 403
    assert client.post("/prompts", headers=user_headers, json={}).status_code == 403
    assert client.get("/ai/models").status_code == 401


def test_admin_can_store_api_key_without_returning_it(tmp_path: Path, monkeypatch) -> None:
    chats = setup_stores(tmp_path, monkeypatch)
    client = TestClient(app)
    headers = register_and_login(client, "admin-secret@example.com", "Admin")
    created = client.post("/admin/model-providers", headers=headers, json={
        "name": "Encrypted Provider", "base_url": "https://provider.example/v1",
        "api_key_env": "MISSING_KEY", "api_key": "front-end-secret",
    })
    assert created.status_code == 201, created.text
    assert created.json()["has_api_key"] is True
    assert "api_key" not in created.json()

    model = client.post(f"/admin/model-providers/{created.json()['id']}/models", headers=headers, json={
        "model_key": "chat-model", "name": "Chat Model", "is_default": True,
    })
    provider, _ = chats.resolve_model(created.json()["id"], model.json()["id"])
    assert provider._resolved_api_key == "front-end-secret"
    raw = next(item for item in chats.admin_providers() if item["id"] == created.json()["id"])
    assert "front-end-secret" not in str(raw)
