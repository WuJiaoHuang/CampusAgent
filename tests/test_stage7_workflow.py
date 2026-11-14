import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool

from campus_agent.agent import AgentService
from campus_agent.config import Settings


class CreateEnrollmentLlm:
    def bind_tools(self, _tools):
        return self

    async def ainvoke(self, _messages):
        return AIMessage(
            content="",
            tool_calls=[
                {"id": "create-1", "name": "create_enrollment", "args": {"training_id": 7}}
            ],
        )


def _decoder(token):
    return {"userId": 1 if token == "user-a" else 2}


def _tools(records, writes):
    async def mine(page: int = 1, size: int = 100):
        return {"ok": True, "data": {"records": list(records), "page": page, "size": size}}

    async def detail(training_id: int):
        return {"ok": True, "data": {"id": training_id, "title": "测试培训"}}

    async def create(training_id: int):
        writes.append(training_id)
        records.append({"enrollmentId": 71, "trainingId": training_id, "status": 1})
        return {"ok": True, "data": {"enrollment_id": 71}}

    return {
        "get_my_enrollments": StructuredTool.from_function(
            coroutine=mine, name="get_my_enrollments", description="报名记录"
        ),
        "get_training_detail": StructuredTool.from_function(
            coroutine=detail, name="get_training_detail", description="培训详情"
        ),
        "create_enrollment": StructuredTool.from_function(
            coroutine=create, name="create_enrollment", description="创建报名"
        ),
    }


@pytest.mark.anyio
async def test_create_requires_interrupt_confirmation_and_verifies(tmp_path):
    records, writes = [], []
    service = AgentService(
        Settings(sqlite_path=tmp_path / "stage7.sqlite3"),
        llm=CreateEnrollmentLlm(),
        tools=_tools(records, writes),
        jwt_decoder=_decoder,
    )
    await service.start()
    pending = await service.chat("报名培训 7", "session-a", "user-a")
    assert pending["status"] == "pending_confirmation"
    assert pending["pending_action"]["tool_name"] == "create_enrollment"
    assert pending["pending_action"]["arguments"] == {"training_id": 7}
    assert writes == []
    with pytest.raises(ValueError):
        await service.confirm(
            "session-a", "user-b", pending["pending_action"]["operation_id"], True
        )
    await service.close()

    restarted = AgentService(
        Settings(sqlite_path=tmp_path / "stage7.sqlite3"),
        llm=CreateEnrollmentLlm(),
        tools=_tools(records, writes),
        jwt_decoder=_decoder,
    )
    await restarted.start()
    completed = await restarted.confirm(
        "session-a", "user-a", pending["pending_action"]["operation_id"], True
    )
    assert completed["answer"] == "操作已完成并核验成功。"
    assert writes == [7]
    with pytest.raises(RuntimeError):
        await restarted.confirm(
            "session-a", "user-a", pending["pending_action"]["operation_id"], True
        )
    await restarted.close()


@pytest.mark.anyio
async def test_cancel_rejection_never_calls_write_tool(tmp_path):
    records, writes = [{"enrollmentId": 71, "trainingId": 7, "status": 1}], []

    class CancelLlm:
        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, _messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "cancel-1",
                        "name": "cancel_enrollment",
                        "args": {"enrollment_id": 71},
                    }
                ],
            )

    async def cancel(enrollment_id: int):
        writes.append(enrollment_id)
        return {"ok": True, "data": {}}

    tools = _tools(records, writes)
    tools["cancel_enrollment"] = StructuredTool.from_function(
        coroutine=cancel, name="cancel_enrollment", description="取消报名"
    )
    service = AgentService(
        Settings(sqlite_path=tmp_path / "cancel.sqlite3"),
        llm=CancelLlm(),
        tools=tools,
        jwt_decoder=_decoder,
    )
    await service.start()
    pending = await service.chat("取消报名", "cancel-session", "user-a")
    rejected = await service.confirm(
        "cancel-session", "user-a", pending["pending_action"]["operation_id"], False
    )
    assert rejected["answer"] == "已拒绝该操作，未执行任何写入。"
    assert writes == []
    await service.close()


@pytest.mark.anyio
async def test_react_runs_two_decision_rounds_and_matches_tool_messages(tmp_path):
    seen = []

    class ReActLlm:
        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, messages):
            seen.append(messages)
            if len(seen) == 1:
                return AIMessage(
                    content="",
                    tool_calls=[{"id": "first", "name": "one", "args": {}}],
                )
            if len(seen) == 2:
                return AIMessage(
                    content="",
                    tool_calls=[{"id": "second", "name": "two", "args": {}}],
                )
            return AIMessage(content="两次查询完成")

    async def one():
        return {"ok": True, "data": {"one": 1}}

    async def two():
        return {"ok": True, "data": {"two": 2}}

    service = AgentService(
        Settings(sqlite_path=tmp_path / "react.sqlite3"),
        llm=ReActLlm(),
        tools={
            "one": StructuredTool.from_function(coroutine=one, name="one", description="one"),
            "two": StructuredTool.from_function(coroutine=two, name="two", description="two"),
        },
        jwt_decoder=_decoder,
    )
    await service.start()
    response = await service.chat("连续查询", "react", "user-a")
    assert response["answer"] == "两次查询完成"
    assert [item["id"] for item in response["tool_calls"]] == ["first", "second"]
    second_round_tools = [item for item in seen[1] if isinstance(item, ToolMessage)]
    assert [item.tool_call_id for item in second_round_tools] == ["first"]
    third_round_tools = [item for item in seen[2] if isinstance(item, ToolMessage)]
    assert [item.tool_call_id for item in third_round_tools] == ["first", "second"]
    await service.close()


@pytest.mark.anyio
async def test_rag_context_is_ephemeral_reference_for_decision(tmp_path):
    seen = []

    class Rag:
        async def search(self, _query, top_k):
            assert top_k == 3
            return [{"text": "报名规则事实", "source_refs": ["EnrollmentServiceImpl"]}]

    class Llm:
        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, messages):
            seen.extend(messages)
            return AIMessage(content="依据知识库回答")

    service = AgentService(
        Settings(sqlite_path=tmp_path / "rag.sqlite3"),
        llm=Llm(),
        rag=Rag(),
        jwt_decoder=_decoder,
    )
    await service.start()
    response = await service.chat("报名规则", "rag", "user-a")
    assert response["citations"][0]["source_refs"] == ["EnrollmentServiceImpl"]
    assert any("报名规则事实" in str(message.content) for message in seen)
    await service.close()
