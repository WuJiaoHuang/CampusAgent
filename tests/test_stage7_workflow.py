import asyncio

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
        return {
            "ok": True,
            "data": {
                "records": list(records),
                "page": page,
                "size": size,
                "total": len(records),
                "pages": 1,
            },
        }

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
    blocked_chat = await service.chat("查询其他课程", "session-a", "user-a")
    assert blocked_chat["status"] == "pending_confirmation"
    assert (
        blocked_chat["pending_action"]["operation_id"]
        == pending["pending_action"]["operation_id"]
    )
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
    results = await asyncio.gather(
        restarted.confirm("session-a", "user-a", pending["pending_action"]["operation_id"], True),
        restarted.confirm("session-a", "user-a", pending["pending_action"]["operation_id"], True),
        return_exceptions=True,
    )
    completed = next(item for item in results if isinstance(item, dict))
    assert completed["answer"] == "操作已完成并核验成功。"
    assert writes == [7]
    assert sum(isinstance(item, RuntimeError) for item in results) == 1
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
async def test_cancel_confirmation_still_verifies_cancelled_state(tmp_path):
    records, writes = [{"enrollmentId": 71, "trainingId": 7, "status": 1}], []

    class CancelLlm:
        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, _messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "cancel-success",
                        "name": "cancel_enrollment",
                        "args": {"enrollment_id": 71},
                    }
                ],
            )

    async def cancel(enrollment_id: int):
        writes.append(enrollment_id)
        records[0]["status"] = 0
        return {"ok": True, "data": {}}

    tools = _tools(records, writes)
    tools["cancel_enrollment"] = StructuredTool.from_function(
        coroutine=cancel, name="cancel_enrollment", description="取消报名"
    )
    service = AgentService(
        Settings(sqlite_path=tmp_path / "cancel-success.sqlite3"),
        llm=CancelLlm(),
        tools=tools,
        jwt_decoder=_decoder,
    )
    await service.start()
    pending = await service.chat("取消报名", "cancel-success", "user-a")
    completed = await service.confirm(
        "cancel-success", "user-a", pending["pending_action"]["operation_id"], True
    )
    assert completed["answer"] == "操作已完成并核验成功。"
    assert writes == [71]
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


@pytest.mark.anyio
async def test_prepare_fails_closed_when_enrollment_lookup_fails(tmp_path):
    writes = []

    async def failed_mine(page: int = 1, size: int = 100):
        return {"ok": False, "error": {"type": "CampusHttpError"}}

    async def detail(training_id: int):
        return {"ok": True, "data": {"id": training_id}}

    async def create(training_id: int):
        writes.append(training_id)
        return {"ok": True, "data": {"enrollment_id": 1}}

    service = AgentService(
        Settings(sqlite_path=tmp_path / "failed-prepare.sqlite3"),
        llm=CreateEnrollmentLlm(),
        tools={
            "get_my_enrollments": StructuredTool.from_function(
                coroutine=failed_mine, name="get_my_enrollments", description="报名记录"
            ),
            "get_training_detail": StructuredTool.from_function(
                coroutine=detail, name="get_training_detail", description="培训详情"
            ),
            "create_enrollment": StructuredTool.from_function(
                coroutine=create, name="create_enrollment", description="创建报名"
            ),
        },
        jwt_decoder=_decoder,
    )
    await service.start()
    response = await service.chat("报名培训 7", "failed-prepare", "user-a")
    assert response["answer"] == "无法准备操作：ToolResultError"
    assert "pending_action" not in response
    assert writes == []
    await service.close()


@pytest.mark.anyio
async def test_prepare_scans_all_pages_before_declaring_no_active_enrollment(tmp_path):
    records = [
        {"enrollmentId": index, "trainingId": index, "status": 1}
        for index in range(1, 101)
    ] + [{"enrollmentId": 101, "trainingId": 777, "status": 1}]
    calls = []

    async def mine(page: int = 1, size: int = 100):
        calls.append(page)
        start = (page - 1) * size
        return {
            "ok": True,
            "data": {
                "records": records[start : start + size],
                "total": len(records),
                "pages": 2,
            },
        }

    async def detail(training_id: int):
        return {"ok": True, "data": {"id": training_id}}

    class ExistingEnrollmentLlm:
        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, _messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "create-existing",
                        "name": "create_enrollment",
                        "args": {"training_id": 777},
                    }
                ],
            )

    service = AgentService(
        Settings(sqlite_path=tmp_path / "pagination.sqlite3"),
        llm=ExistingEnrollmentLlm(),
        tools={
            "get_my_enrollments": StructuredTool.from_function(
                coroutine=mine, name="get_my_enrollments", description="报名记录"
            ),
            "get_training_detail": StructuredTool.from_function(
                coroutine=detail, name="get_training_detail", description="培训详情"
            ),
        },
        jwt_decoder=_decoder,
    )
    await service.start()
    response = await service.chat("报名培训 7", "pagination", "user-a")
    assert response["answer"] == "无法准备操作：ValueError"
    assert "pending_action" not in response
    assert calls == [1, 2]
    await service.close()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("verification_outcome", "expected_error_type"),
    [
        ("exception", "RuntimeError"),
        ("business_error", "CampusHttpError"),
        ("malformed", "ToolResultError"),
    ],
)
async def test_verification_failure_marks_operation_uncertain(
    tmp_path, verification_outcome, expected_error_type
):
    records, writes, mine_calls = [], [], 0

    async def mine(page: int = 1, size: int = 100):
        nonlocal mine_calls
        mine_calls += 1
        if mine_calls > 1:
            if verification_outcome == "exception":
                raise RuntimeError("gateway unavailable")
            if verification_outcome == "business_error":
                return {"ok": False, "error": {"type": "CampusHttpError"}}
            return {"ok": True, "data": {"records": "invalid", "total": 0, "pages": 1}}
        return {
            "ok": True,
            "data": {"records": records, "total": 0, "pages": 1, "page": page, "size": size},
        }

    async def detail(training_id: int):
        return {"ok": True, "data": {"id": training_id}}

    async def create(training_id: int):
        writes.append(training_id)
        return {"ok": True, "data": {"enrollment_id": 71}}

    service = AgentService(
        Settings(sqlite_path=tmp_path / f"verify-{verification_outcome}.sqlite3"),
        llm=CreateEnrollmentLlm(),
        tools={
            "get_my_enrollments": StructuredTool.from_function(
                coroutine=mine, name="get_my_enrollments", description="报名记录"
            ),
            "get_training_detail": StructuredTool.from_function(
                coroutine=detail, name="get_training_detail", description="培训详情"
            ),
            "create_enrollment": StructuredTool.from_function(
                coroutine=create, name="create_enrollment", description="创建报名"
            ),
        },
        jwt_decoder=_decoder,
    )
    await service.start()
    pending = await service.chat("报名", f"verify-{verification_outcome}", "user-a")
    result = await service.confirm(
        f"verify-{verification_outcome}", "user-a", pending["pending_action"]["operation_id"], True
    )
    assert result["answer"] == "操作结果待核实；系统不会自动重试。"
    action = service.actions.get(
        pending["pending_action"]["operation_id"],
        service._identity("user-a", f"verify-{verification_outcome}")[1],
        "1",
    )
    assert action["status"] == "UNCERTAIN"
    assert action["result"]["error_type"] == expected_error_type
    assert writes == [7]
    await service.close()


@pytest.mark.anyio
async def test_checkpoint_mismatch_marks_confirmed_operation_uncertain(tmp_path):
    records, writes = [], []
    service = AgentService(
        Settings(sqlite_path=tmp_path / "mismatch.sqlite3"),
        llm=CreateEnrollmentLlm(),
        tools=_tools(records, writes),
        jwt_decoder=_decoder,
    )
    await service.start()
    thread_id = service._identity("user-a", "mismatch")[1]
    action = service.actions.create(
        thread_id=thread_id,
        user_id="1",
        tool_name="create_enrollment",
        arguments={"training_id": 7},
        summary={"operation": "create_enrollment", "before_enrollment": None},
    )
    assert service.actions.approve(action["operation_id"], thread_id, "1")
    blocked = await service.chat("继续", "mismatch", "user-a")
    assert blocked["answer"] == "操作已确认但尚未恢复执行，请使用原 operation ID 再次明确确认。"
    assert writes == []
    with pytest.raises(RuntimeError, match="待核实"):
        await service.confirm("mismatch", "user-a", action["operation_id"], True)
    stored = service.actions.get(action["operation_id"], thread_id, "1")
    assert stored["status"] == "UNCERTAIN"
    assert writes == []
    await service.close()


@pytest.mark.anyio
async def test_executing_recovery_only_reads_and_unblocks_next_chat(tmp_path):
    records, writes = [], []
    service = AgentService(
        Settings(sqlite_path=tmp_path / "executing.sqlite3"),
        llm=None,
        tools=_tools(records, writes),
        jwt_decoder=_decoder,
    )
    await service.start()
    thread_id = service._identity("user-a", "executing")[1]
    action = service.actions.create(
        thread_id=thread_id,
        user_id="1",
        tool_name="create_enrollment",
        arguments={"training_id": 7},
        summary={"operation": "create_enrollment", "before_enrollment": None},
    )
    assert service.actions.approve(action["operation_id"], thread_id, "1")
    assert service.actions.begin_execution(action["operation_id"], thread_id, "1")
    recovered = await service.chat("继续", "executing", "user-a")
    assert recovered["answer"] == "遗留操作结果待核实，未自动重试写入。"
    assert writes == []
    stored = service.actions.get(action["operation_id"], thread_id, "1")
    assert stored["status"] == "UNCERTAIN"
    next_chat = await service.chat("新问题", "executing", "user-a")
    assert next_chat["answer"] == "我可以帮助查询课程、报名和学习进度。"
    await service.close()
