from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

from campus_agent.agent.memory import ConversationMemory


class AgentService:
    def __init__(
        self, settings, llm: Any = None, rag: Any = None,
        tool_call: Callable[..., Awaitable[Any]] | None = None,
    ) -> None:
        self.settings, self.llm, self.rag, self.tool_call = settings, llm, rag, tool_call
        self.memory = ConversationMemory(settings.sqlite_path)
        self.calls: dict[str, int] = {}

    async def chat(self, message: str, session_id: str, jwt: str) -> dict[str, Any]:
        if not jwt:
            raise ValueError("Authorization JWT required")
        key = self.memory.user_key(jwt, session_id)
        history = self.memory.load(key)
        count = self.calls.get(key, 0)
        if count >= 8:
            raise RuntimeError("模型调用次数已达到本次请求上限")
        self.calls[key] = count + 1
        citations: list[dict[str, Any]] = []
        tools: list[dict[str, Any]] = []
        answer = await self._answer(message, history, jwt, citations, tools)
        history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer},
        ])
        self.memory.save(key, history[-20:])
        return {
            "answer": answer, "session_id": session_id,
            "tool_calls": tools, "citations": citations,
        }

    async def _answer(
        self, message: str, history: list[dict[str, str]], jwt: str, citations: list, tools: list
    ) -> str:
        if self.llm is not None:
            result = await self.llm.ainvoke(history + [{"role": "user", "content": message}])
            return getattr(result, "content", str(result))
        if self.rag is not None:
            hits = self.rag.search(message, top_k=3)
            citations.extend(hits)
        if self.tool_call and (m := re.search(r"(培训|课程|报名|进度).*?(\d+)", message)):
            name = (
                "get_training_detail"
                if "详情" in message or "课程" in message
                else "get_training_progress"
            )
            data = await self.tool_call(name, int(m.group(2)), jwt=jwt)
            tools.append({"name": name, "ok": bool(data.get("ok", True))})
            return str(data.get("data", data))
        return "我可以帮助查询课程详情、课程目录、报名记录和学习进度。请提供培训或课时编号。"
