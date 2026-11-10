from __future__ import annotations

import jwt
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from campus_agent.agent import AgentService
from campus_agent.config import Settings

app = FastAPI(title="CampusAgent", version="0.1.0")
settings = Settings()


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
