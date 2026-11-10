from __future__ import annotations

import json
from typing import Any, TypedDict

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
    ai_message: AIMessage
    tool_messages: list[ToolMessage]
    answer: str


class AgentService:
    def __init__(self, settings, llm=None, rag=None, tools=None, jwt_decoder=None):
        self.settings, self.rag = settings, rag
        self.llm, self.tools, self.jwt_decoder = llm, tools or {}, jwt_decoder
        self.memory = ConversationMemory(settings.sqlite_path)
        self._graph_builder = StateGraph(AgentState)
        self._graph_builder.add_node("retrieve", self._retrieve)
        self._graph_builder.add_node("decide", self._decide)
        self._graph_builder.add_node("execute", self._execute)
        self._graph_builder.add_node("answer", self._answer)
        self._graph_builder.add_edge(START, "retrieve")
        self._graph_builder.add_edge("retrieve", "decide")
        self._graph_builder.add_conditional_edges(
            "decide", lambda s: "execute" if s.get("tool_calls") else "answer"
        )
        self._graph_builder.add_edge("execute", "answer")
        self._graph_builder.add_edge("answer", END)
        self._checkpoint_context = None
        self.graph = None

    async def start(self) -> None:
        if self.graph is not None:
            return
        self._checkpoint_context = AsyncSqliteSaver.from_conn_string(
            str(self.settings.sqlite_path)
        )
        saver = await self._checkpoint_context.__aenter__()
        self.graph = self._graph_builder.compile(checkpointer=saver)

    async def close(self) -> None:
        if self._checkpoint_context is not None:
            await self._checkpoint_context.__aexit__(None, None, None)
            self._checkpoint_context = None
            self.graph = None

    async def chat(self, message: str, session_id: str, jwt: str) -> dict[str, Any]:
        if self.graph is None:
            await self.start()
        claims = self.jwt_decoder(jwt) if self.jwt_decoder else None
        user_id = claims.get("userId") if claims else None
        if user_id is None and claims:
            user_id = claims.get("sub")
        if user_id is None:
            raise ValueError("JWT 无效")
        key = ConversationMemory.user_key(str(user_id), session_id)
        jwt_context_token = None
        if hasattr(self, "mcp_bridge"):
            jwt_context_token = self.mcp_bridge.set_jwt(jwt)
        history = self.memory.load(key)
        try:
            state = await self.graph.ainvoke(
                {"message": message, "history": history},
                config={"configurable": {"thread_id": key}},
            )
        finally:
            if jwt_context_token is not None:
                self.mcp_bridge.reset_jwt(jwt_context_token)
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
