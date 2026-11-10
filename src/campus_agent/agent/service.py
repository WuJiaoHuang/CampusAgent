from __future__ import annotations

import json
from typing import Any, TypedDict

import aiosqlite
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from campus_agent.agent.memory import ConversationMemory


class AgentState(TypedDict, total=False):
    message: str
    history: list[dict[str, str]]
    jwt: str
    context: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    answer: str


class AgentService:
    def __init__(self, settings, llm=None, rag=None, tools=None, jwt_decoder=None):
        self.settings, self.rag = settings, rag
        self.llm, self.tools, self.jwt_decoder = llm, tools or {}, jwt_decoder
        self.memory = ConversationMemory(settings.sqlite_path)
        graph = StateGraph(AgentState)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("decide", self._decide)
        graph.add_node("execute", self._execute)
        graph.add_node("answer", self._answer)
        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "decide")
        graph.add_conditional_edges(
            "decide", lambda s: "execute" if s.get("tool_calls") else "answer"
        )
        graph.add_edge("execute", "answer")
        graph.add_edge("answer", END)
        try:
            self._checkpoint_connection = aiosqlite.connect(str(settings.sqlite_path))
            self.graph = graph.compile(checkpointer=AsyncSqliteSaver(self._checkpoint_connection))
        except RuntimeError:
            self._checkpoint_connection = None
            self.graph = graph.compile()

    async def chat(self, message: str, session_id: str, jwt: str) -> dict[str, Any]:
        claims = self.jwt_decoder(jwt) if self.jwt_decoder else None
        if not claims or "sub" not in claims:
            raise ValueError("JWT 无效")
        key = ConversationMemory.user_key(str(claims["sub"]), session_id)
        if hasattr(self, "mcp_bridge"):
            self.mcp_bridge.set_jwt(jwt)
        history = self.memory.load(key)
        state = await self.graph.ainvoke(
            {"message": message, "history": history},
            config={"configurable": {"thread_id": key, "request_jwt": jwt}},
        )
        history.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": state["answer"]},
            ]
        )
        self.memory.save(key, history[-20:])
        return {
            "answer": state["answer"],
            "session_id": session_id,
            "tool_calls": state.get("tool_calls", []),
            "citations": state.get("context", []),
        }

    async def _retrieve(self, state):
        if self.rag:
            result = self.rag.search(state["message"], top_k=3)
            state["context"] = await result if hasattr(result, "__await__") else result
        return state

    async def _decide(self, state):
        if not self.llm:
            state["tool_calls"] = []
            return state
        model = self.llm.bind_tools(list(self.tools.values())) if self.tools else self.llm
        messages = [
            HumanMessage(content=item["content"])
            if item["role"] == "user"
            else AIMessage(content=item["content"])
            for item in state["history"]
        ]
        result = await model.ainvoke(messages + [HumanMessage(content=state["message"])])
        state["ai_message"] = result
        state["tool_calls"] = list(getattr(result, "tool_calls", []))
        return state

    async def _execute(self, state, config):
        results = []
        ai_message = state.get("ai_message")
        if ai_message is None:
            state["tool_results"] = results
            return state
        calls = state.get("tool_calls", [])
        for index, call in enumerate(calls):
            if index >= self.settings.max_tool_calls_per_request:
                results.append({"name": call.get("name"), "error": "tool call limit exceeded"})
                continue
            tool = self.tools.get(call.get("name"))
            if not tool:
                results.append({"name": call.get("name"), "error": "unknown tool"})
                continue
            try:
                results.append(
                    {
                        "name": call["name"],
                        "data": await tool.ainvoke(call.get("args", {})),
                    }
                )
            except Exception as exc:
                results.append({"name": call["name"], "error": type(exc).__name__})
        state["tool_messages"] = [
            ToolMessage(
                content=json.dumps(item.get("data", item.get("error")), ensure_ascii=False),
                tool_call_id=call.get("id", "missing"),
                name=call.get("name", "tool"),
            )
            for call, item in zip(calls, results, strict=True)
        ]
        state["tool_results"] = results
        return state

    async def _answer(self, state):
        if self.llm:
            messages = [HumanMessage(content=item["content"]) for item in state["history"]]
            messages.append(HumanMessage(content=state["message"]))
            if state.get("ai_message"):
                messages.append(state["ai_message"])
            messages.extend(state.get("tool_messages", []))
            result = await self.llm.ainvoke(messages)
            state["answer"] = getattr(result, "content", str(result))
        else:
            state["answer"] = "我可以帮助查询课程、报名和学习进度。"
        return state
