from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from campus_agent.agent.memory import ConversationMemory


class AgentState(MessagesState, total=False):
    """Persisted graph state; ``messages`` uses LangGraph's add_messages reducer."""

    context: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    answer: str


class AgentService:
    def __init__(self, settings, llm=None, rag=None, tools=None, jwt_decoder=None):
        self.settings, self.rag = settings, rag
        self.llm, self.tools, self.jwt_decoder = llm, tools or {}, jwt_decoder
        self._graph_builder = StateGraph(AgentState)
        self._graph_builder.add_node("retrieve", self._retrieve)
        self._graph_builder.add_node("decide", self._decide)
        self._graph_builder.add_node("execute", self._execute)
        self._graph_builder.add_node("answer", self._answer)
        self._graph_builder.add_edge(START, "retrieve")
        self._graph_builder.add_edge("retrieve", "decide")
        self._graph_builder.add_conditional_edges(
            "decide", lambda state: "execute" if state.get("tool_calls") else "answer"
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
        try:
            saver = await self._checkpoint_context.__aenter__()
            self.graph = self._graph_builder.compile(checkpointer=saver)
        except Exception:
            await self._checkpoint_context.__aexit__(None, None, None)
            self._checkpoint_context = None
            raise

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
        try:
            state = await self.graph.ainvoke(
                {
                    "messages": [HumanMessage(content=message)],
                    # These fields only describe this HTTP request. Resetting
                    # them prevents an earlier turn's summary leaking into the
                    # current response while messages remain checkpointed.
                    "context": [],
                    "tool_calls": [],
                    "answer": "",
                },
                config={"configurable": {"thread_id": key}},
            )
        finally:
            if jwt_context_token is not None:
                self.mcp_bridge.reset_jwt(jwt_context_token)
        return {
            "answer": state["answer"],
            "session_id": session_id,
            "tool_calls": state.get("tool_calls", []),
            "citations": state.get("context", []),
        }

    @staticmethod
    def _latest_human_message(messages: list[BaseMessage]) -> HumanMessage:
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return message
        raise ValueError("缺少用户消息")

    @staticmethod
    def _latest_ai_message(messages: list[BaseMessage]) -> AIMessage | None:
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return message
        return None

    async def _retrieve(self, state: AgentState) -> dict[str, Any]:
        if not self.rag:
            return {"context": []}
        query = self._latest_human_message(state["messages"]).text
        result = self.rag.search(query, top_k=3)
        context = await result if hasattr(result, "__await__") else result
        return {"context": context}

    async def _decide(self, state: AgentState) -> dict[str, Any]:
        if not self.llm:
            return {"tool_calls": []}
        model = self.llm.bind_tools(list(self.tools.values())) if self.tools else self.llm
        result = await model.ainvoke(state["messages"])
        if not isinstance(result, AIMessage):
            raise TypeError("模型必须返回 AIMessage")
        calls = list(result.tool_calls)
        return {"messages": [result], "tool_calls": calls}

    async def _execute(self, state: AgentState) -> dict[str, Any]:
        ai_message = self._latest_ai_message(state["messages"])
        calls = list(ai_message.tool_calls) if ai_message is not None else []
        messages: list[ToolMessage] = []
        for index, call in enumerate(calls):
            name = call.get("name", "tool")
            call_id = call.get("id", "missing")
            if index >= self.settings.max_tool_calls_per_request:
                content = {"error": "tool call limit exceeded"}
            elif (tool := self.tools.get(name)) is None:
                content = {"error": "unknown tool"}
            else:
                try:
                    content = await tool.ainvoke(call.get("args", {}))
                except Exception as exc:
                    content = {"error": type(exc).__name__}
            messages.append(
                ToolMessage(
                    content=json.dumps(content, ensure_ascii=False),
                    tool_call_id=call_id,
                    name=name,
                )
            )
        return {"messages": messages}

    async def _answer(self, state: AgentState) -> dict[str, Any]:
        latest = self._latest_ai_message(state["messages"])
        # A tool-free response from decide is already the final answer. Calling
        # the LLM again would waste a request and duplicate the assistant turn.
        if latest is not None and not latest.tool_calls:
            return {"answer": str(latest.content)}
        if self.llm:
            result = await self.llm.ainvoke(state["messages"])
            if not isinstance(result, AIMessage):
                raise TypeError("模型必须返回 AIMessage")
            return {"messages": [result], "answer": str(result.content)}

        fallback = AIMessage(content="我可以帮助查询课程、报名和学习进度。")
        return {"messages": [fallback], "answer": str(fallback.content)}
