from uuid import uuid4

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
            json={"message": "查询培训16001详情", "session_id": f"tool-cycle-{uuid4()}"},
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


def test_fake_llm_multiple_tool_messages_and_new_turn_reset(monkeypatch):
    _patch_lifespan(monkeypatch)
    observed = {"calls": [], "second_turn_messages": None}

    async def available(training_id: int):
        return {"training_id": training_id}

    async def broken():
        raise RuntimeError("offline")

    class FakeLlm:
        def __init__(self):
            self.invocations = 0

        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            self.invocations += 1
            observed["calls"].append(messages)
            if self.invocations == 1:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {"id": "ok", "name": "available", "args": {"training_id": 1}},
                        {"id": "missing", "name": "not_registered", "args": {}},
                        {"id": "broken", "name": "broken", "args": {}},
                        {"id": "later", "name": "available", "args": {"training_id": 2}},
                    ],
                )
            if self.invocations == 2:
                return AIMessage(content="工具结果已收到")
            observed["second_turn_messages"] = messages
            return AIMessage(content="第二轮没有工具")

    api.service.llm = FakeLlm()
    api.service.tools["available"] = StructuredTool.from_function(
        coroutine=available, name="available", description="可用工具"
    )
    api.service.tools["broken"] = StructuredTool.from_function(
        coroutine=broken, name="broken", description="失败工具"
    )
    monkeypatch.setattr(api.service.settings, "max_tool_calls_per_request", 3)
    session_id = f"many-tools-{uuid4()}"
    with TestClient(api.app) as client:
        first = client.post(
            "/agent/chat",
            json={"message": "执行多个工具", "session_id": session_id},
            headers={"Authorization": "Bearer user-a-token"},
        )
        second = client.post(
            "/agent/chat",
            json={"message": "继续", "session_id": session_id},
            headers={"Authorization": "Bearer user-a-token"},
        )
    assert first.status_code == second.status_code == 200
    assert [call["id"] for call in first.json()["tool_calls"]] == [
        "ok",
        "missing",
        "broken",
        "later",
    ]
    assert second.json()["tool_calls"] == []
    tool_messages = [
        item for item in observed["calls"][1] if isinstance(item, ToolMessage)
    ]
    assert [item.tool_call_id for item in tool_messages] == ["ok", "missing", "broken", "later"]
    assert "training_id" in tool_messages[0].content
    assert "unknown tool" in tool_messages[1].content
    assert "RuntimeError" in tool_messages[2].content
    assert "tool call limit exceeded" in tool_messages[3].content
    assert observed["second_turn_messages"] is not None
    assert all(
        not isinstance(message, ToolMessage)
        for message in observed["second_turn_messages"][-2:]
    )
