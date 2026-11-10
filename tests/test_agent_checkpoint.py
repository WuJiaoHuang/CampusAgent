import sqlite3

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from campus_agent.agent import AgentService
from campus_agent.config import Settings


class RecordingLlm:
    def __init__(self, answer):
        self.answer = answer
        self.seen = []

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self.seen.append(messages)
        return AIMessage(content=self.answer)


@pytest.mark.anyio
async def test_sqlite_checkpoint_restart_and_user_isolation(tmp_path):
    db = tmp_path / "checkpoint.sqlite3"
    settings = Settings(sqlite_path=db)
    def decoder(token):
        return {"userId": 1001 if token.startswith("user-a") else 2002}

    first_llm = RecordingLlm("第一轮答案")
    first = AgentService(settings, llm=first_llm, jwt_decoder=decoder)
    await first.start()
    await first.chat("第一轮问题", "shared-session", "user-a-old-token")
    await first.close()
    first.memory.close()

    second_llm = RecordingLlm("第二轮答案")
    second = AgentService(settings, llm=second_llm, jwt_decoder=decoder)
    await second.start()
    await second.chat("继续说明", "shared-session", "user-a-refreshed-token")
    flattened = " ".join(str(message.content) for call in second_llm.seen for message in call)
    assert "第一轮问题" in flattened
    assert "第一轮答案" in flattened
    second_round_messages = second_llm.seen[0]
    assert any(
        isinstance(message, HumanMessage) and message.content == "第一轮问题"
        for message in second_round_messages
    )
    assert any(
        isinstance(message, AIMessage) and message.content == "第一轮答案"
        for message in second_round_messages
    )

    other_llm = RecordingLlm("用户 B 答案")
    second.llm = other_llm
    await second.chat("用户 B 问题", "shared-session", "user-b-token")
    other_flattened = " ".join(
        str(message.content) for call in other_llm.seen for message in call
    )
    assert "第一轮问题" not in other_flattened
    await second.close()
    second.memory.close()

    connection = sqlite3.connect(db)
    assert connection.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0] > 0
    connection.close()
    raw = db.read_bytes()
    assert b"user-a-old-token" not in raw
    assert b"user-a-refreshed-token" not in raw
    assert b"user-b-token" not in raw
