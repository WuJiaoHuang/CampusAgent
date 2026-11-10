from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool

import campus_agent.api as api


class FakeStore:
    def __init__(self, *args, **kwargs):
        pass

    def count(self):
        return 1

    def search(self, query, top_k):
        return []


class FakeBridge:
    def __init__(self, *args, **kwargs):
        self.schemas = {}

    async def discover(self):
        return []

    def set_jwt(self, token):
        return token

    def reset_jwt(self, token):
        pass


def _patch_lifespan(monkeypatch):
    monkeypatch.setattr(api, "BgeEmbedding", lambda *args, **kwargs: object())
    monkeypatch.setattr(api, "KnowledgeStore", FakeStore)
    monkeypatch.setattr(api, "McpBridge", FakeBridge)
    api.service.jwt_decoder = lambda token: {"sub": token}


def test_chat_requires_jwt(monkeypatch):
    _patch_lifespan(monkeypatch)
    with TestClient(api.app) as client:
        response = client.post("/agent/chat", json={"message": "你好", "session_id": "s1"})
    assert response.status_code == 401


def test_chat_is_user_scoped(monkeypatch):
    _patch_lifespan(monkeypatch)
    payload = {"message": "你好", "session_id": "same"}
    with TestClient(api.app) as client:
        first = client.post(
            "/agent/chat", json=payload, headers={"Authorization": "Bearer a"}
        )
        second = client.post(
            "/agent/chat", json=payload, headers={"Authorization": "Bearer b"}
        )
    assert first.status_code == second.status_code == 200
    assert first.json()["session_id"] == "same"


def test_fake_llm_http_tool_message_cycle(monkeypatch):
    _patch_lifespan(monkeypatch)
    observed = {"tool_args": None, "second_messages": None}

    async def fake_detail(training_id: int):
        observed["tool_args"] = training_id
        return {"id": training_id, "title": "Python 入门"}

    class FakeLlm:
        calls = 0

        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "id": "call_001",
                        "name": "get_training_detail",
                        "args": {"training_id": 16001},
                    }],
                )
            observed["second_messages"] = messages
            return AIMessage(content="培训名称是 Python 入门")

    api.service.llm = FakeLlm()
    api.service.tools["get_training_detail"] = StructuredTool.from_function(
        coroutine=fake_detail,
        name="get_training_detail",
        description="查询培训详情",
    )
    with TestClient(api.app) as client:
        response = client.post(
            "/agent/chat",
            json={"message": "查询培训16001详情", "session_id": "tool-cycle-v2"},
            headers={"Authorization": "Bearer user-a-token"},
        )
    assert response.status_code == 200
    assert response.json()["answer"] == "培训名称是 Python 入门"
    assert observed["tool_args"] == 16001
    tool_messages = [m for m in observed["second_messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call_001"
    assert "Python 入门" in tool_messages[0].content
    assert all("user-a-token" not in str(message) for message in observed["second_messages"])
