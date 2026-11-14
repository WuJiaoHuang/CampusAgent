import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from campus_agent.agent.mcp_bridge import McpBridge
from campus_agent.api import _mcp_args_model
from campus_agent.campus_client.exceptions import CampusHttpError
from campus_agent.mcp_server.server import create_server


class FakeClient:
    def __init__(self):
        self.calls = []

    async def get_training_detail(self, training_id):
        self.calls.append(("detail", training_id))
        return {"id": training_id, "title": "测试培训"}

    async def get_training_catalog(self, training_id):
        self.calls.append(("catalog", training_id))
        return {"trainingId": training_id, "courses": []}

    async def get_my_enrollments(self, **kwargs):
        self.calls.append(("enrollments", kwargs))
        return {"records": [], "total": 0, **kwargs}

    async def get_training_progress(self, training_id):
        self.calls.append(("training_progress", training_id))
        return {"trainingId": training_id, "progressRatio": 0.0}

    async def get_lesson_progress(self, lesson_id):
        self.calls.append(("lesson_progress", lesson_id))
        return {"lessonId": lesson_id, "progressSeconds": 0}

    async def get_chapter_progress(self, chapter_id):
        self.calls.append(("chapter_progress", chapter_id))
        return {"chapterId": chapter_id, "progressRatio": 0.0}

    async def create_enrollment(self, training_id):
        self.calls.append(("create", training_id))
        return 9001

    async def cancel_enrollment(self, enrollment_id):
        self.calls.append(("cancel", enrollment_id))


@pytest.mark.anyio
async def test_real_stdio_schemas_create_exact_langchain_argument_models():
    bridge = McpBridge(Path.cwd(), "", "http://localhost")
    names = await bridge.discover()
    assert set(names) == {
        "get_training_detail",
        "get_training_catalog",
        "get_my_enrollments",
        "get_training_progress",
        "get_lesson_progress",
        "get_chapter_progress",
        "create_enrollment",
        "cancel_enrollment",
    }
    models = {
        name: _mcp_args_model(name, definition["input_schema"])
        for name, definition in bridge.schemas.items()
    }
    assert set(models["get_training_detail"].model_fields) == {"training_id"}
    assert models["get_training_detail"](training_id=16001).training_id == 16001
    with pytest.raises(ValidationError):
        models["get_training_detail"]()
    enrollment = models["get_my_enrollments"]()
    assert (enrollment.page, enrollment.size, enrollment.status) == (1, 10, None)
    assert models["get_my_enrollments"](status=1).status == 1
    assert models["create_enrollment"](training_id=1).training_id == 1
    assert models["cancel_enrollment"](enrollment_id=1).enrollment_id == 1
    for model in models.values():
        assert "jwt" not in model.model_fields
        assert "userId" not in model.model_fields


@pytest.mark.anyio
async def test_tools_are_discoverable_and_map_arguments():
    client = FakeClient()
    server = create_server(client)
    tools = await server.list_tools()

    assert {tool.name for tool in tools} == {
        "get_training_detail",
        "get_training_catalog",
        "get_my_enrollments",
        "get_training_progress",
        "get_lesson_progress",
        "get_chapter_progress",
        "create_enrollment",
        "cancel_enrollment",
    }
    result = await server.call_tool("get_my_enrollments", {"page": 2, "size": 20, "status": 1})
    assert result.is_error is False
    assert result.structured_content["data"]["page"] == 2
    assert client.calls[-1] == ("enrollments", {"page": 2, "size": 20, "status": 1})
    created = await server.call_tool("create_enrollment", {"training_id": 1})
    assert created.structured_content["data"]["enrollment_id"] == 9001
    await server.call_tool("cancel_enrollment", {"enrollment_id": 9001})
    assert client.calls[-1] == ("cancel", 9001)


@pytest.mark.anyio
async def test_tool_validation_rejects_invalid_ids_and_pagination():
    server = create_server(FakeClient())
    with pytest.raises(Exception, match="正整数"):
        await server.call_tool("get_training_detail", {"training_id": 0})
    with pytest.raises(Exception, match="1 到 100"):
        await server.call_tool("get_my_enrollments", {"page": 1, "size": 101})
    with pytest.raises(Exception, match="status"):
        await server.call_tool("get_my_enrollments", {"status": 3})


@pytest.mark.anyio
async def test_tool_maps_gateway_errors_without_sensitive_body():
    class ErrorClient(FakeClient):
        async def get_training_detail(self, training_id):
            raise CampusHttpError(
                401,
                "/training/get/1",
                "token=secret-jwt password=secret-password",
            )

    result = await create_server(ErrorClient()).call_tool("get_training_detail", {"training_id": 1})
    assert result.structured_content["ok"] is False
    assert result.structured_content["error"]["status_code"] == 401
    assert "secret-jwt" not in result.structured_content["error"]["message"]
    assert "secret-password" not in result.structured_content["error"]["message"]


@pytest.mark.anyio
async def test_stdio_client_discovers_and_calls_server():
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    environment = os.environ.copy()
    environment.pop("CAMPUS_AGENT_JWT_TOKEN", None)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "campus_agent.mcp_server.server"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == 8
            result = await session.call_tool("get_training_detail", {"training_id": 0})
            assert result.is_error is True
