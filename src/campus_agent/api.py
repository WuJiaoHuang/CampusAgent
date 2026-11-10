from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import jwt
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from campus_agent.agent import AgentService
from campus_agent.agent.mcp_bridge import McpBridge
from campus_agent.config import Settings
from campus_agent.rag.documents import load_markdown_chunks
from campus_agent.rag.embeddings import BgeEmbedding
from campus_agent.rag.store import KnowledgeStore

settings = Settings()


class RetrieverAdapter:
    def __init__(self, store):
        self.store = store

    async def search(self, query: str, top_k: int = 3):
        if not 1 <= top_k <= 10:
            raise ValueError("top_k must be between 1 and 10")
        import asyncio

        results = await asyncio.to_thread(self.store.search, query, top_k)
        return [
            {
                "text": item.text,
                "distance": item.distance,
                "source_path": item.source_path,
                "heading_path": item.heading_path,
                "source_refs": list(item.source_refs),
            }
            for item in results
        ]


def decode_jwt(token: str):
    if not settings.jwt_secret.get_secret_value():
        return None
    try:
        return jwt.decode(
            token, settings.jwt_secret.get_secret_value(), algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None


llm = None
if settings.llm_api_key.get_secret_value() and settings.llm_model:
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=str(settings.llm_base_url),
        model=settings.llm_model,
        timeout=settings.http_timeout_seconds,
        max_retries=2,
    )
service = AgentService(settings, llm=llm, jwt_decoder=decode_jwt)


@asynccontextmanager
async def lifespan(_app):
    if not settings.knowledge_dir.exists():
        raise RuntimeError(f"知识库目录不存在: {settings.knowledge_dir}")
    embedder = BgeEmbedding(
        settings.embedding_model, settings.model_cache_dir, settings.embedding_batch_size
    )
    store = KnowledgeStore(settings.vector_db_path, embedder)
    if store.count() == 0:
        chunks = load_markdown_chunks(settings.knowledge_dir)
        if not chunks:
            raise RuntimeError("知识库为空，请先运行 uv run campus-agent-rag build")
        store.sync(chunks, settings.embedding_batch_size)

    adapter = RetrieverAdapter(store)

    async def search_knowledge(query: str, top_k: int = 3):
        return await adapter.search(query, top_k)

    service.rag = adapter
    bridge = McpBridge(Path.cwd(), settings.jwt_token.get_secret_value(), str(settings.gateway_url))
    service.mcp_bridge = bridge
    names = await bridge.discover()
    from langchain_core.tools import StructuredTool

    service.tools["search_knowledge"] = StructuredTool.from_function(
        coroutine=search_knowledge,
        name="search_knowledge",
        description="检索 CampusAgent 课程规则知识库并返回来源引用",
    )

    for name in names:

        async def invoke(_name=name, jwt: str = "", **kwargs):
            return await bridge.call(_name, kwargs, jwt)

        service.tools[name] = StructuredTool.from_function(
            coroutine=invoke, name=name, description=f"CampusTrain MCP 只读工具 {name}"
        )
    yield


app = FastAPI(title="CampusAgent", version="0.1.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(min_length=1, max_length=128)


@app.post("/agent/chat")
async def chat(request: ChatRequest, authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 Bearer JWT")
    jwt = authorization[7:].strip()
    if not jwt:
        raise HTTPException(status_code=401, detail="缺少 Bearer JWT")
    try:
        return await service.chat(request.message, request.session_id, jwt)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Agent 调用失败") from exc
