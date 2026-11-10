from __future__ import annotations

import json
from typing import Any, TypedDict

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
        self.graph = graph.compile()

    async def chat(self, message: str, session_id: str, jwt: str) -> dict[str, Any]:
        claims = self.jwt_decoder(jwt) if self.jwt_decoder else None
        if not claims or "sub" not in claims:
            raise ValueError("JWT 无效")
        key = ConversationMemory.user_key(str(claims["sub"]), session_id)
        history = self.memory.load(key)
        state = await self.graph.ainvoke({"message": message, "history": history, "jwt": jwt})
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
        result = await model.ainvoke(
            state["history"] + [{"role": "user", "content": state["message"]}]
        )
        state["tool_calls"] = list(getattr(result, "tool_calls", []))
        return state

    async def _execute(self, state):
        results = []
        for call in state.get("tool_calls", [])[: self.settings.max_tool_calls_per_request]:
            tool = self.tools.get(call.get("name"))
            if not tool:
                results.append({"name": call.get("name"), "error": "unknown tool"})
                continue
            try:
                results.append(
                    {
                        "name": call["name"],
                        "data": await tool(**call.get("args", {}), jwt=state["jwt"]),
                    }
                )
            except Exception as exc:
                results.append({"name": call["name"], "error": type(exc).__name__})
        state["tool_results"] = results
        return state

    async def _answer(self, state):
        if self.llm:
            context = json.dumps(
                {"context": state.get("context", []), "results": state.get("tool_results", [])},
                ensure_ascii=False,
            )
            result = await self.llm.ainvoke(
                state["history"]
                + [
                    {"role": "user", "content": state["message"]},
                    {"role": "system", "content": context},
                ]
            )
            state["answer"] = getattr(result, "content", str(result))
        else:
            state["answer"] = "我可以帮助查询课程、报名和学习进度。"
        return state
