"""Read-only MCP tool registration for CampusTrain."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from campus_agent.campus_client.client import CampusTrainClient
from campus_agent.campus_client.exceptions import CampusClientError


def _positive_id(value: int, name: str) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ToolError(f"{name} 必须是正整数")
    return value


def _page(value: int, name: str, maximum: int) -> int:
    if isinstance(value, bool) or value < 1 or value > maximum:
        raise ToolError(f"{name} 必须在 1 到 {maximum} 之间")
    return value


def _success(data: Mapping[str, Any]) -> dict[str, Any]:
    return {"ok": True, "data": dict(data)}


def _failure(error: CampusClientError) -> dict[str, Any]:
    status_code = getattr(error, "status_code", None)
    return {
        "ok": False,
        "error": {
            "type": type(error).__name__,
            "message": str(error),
            **({"status_code": status_code} if status_code is not None else {}),
        },
    }


def register_tools(server: MCPServer, client: CampusTrainClient) -> MCPServer:
    """Register six read-only tools against a reusable CampusTrain client."""

    @server.tool(
        description="查询培训详情。需要当前用户 JWT；training_id 必须是正整数。只读操作。",
        structured_output=True,
    )
    async def get_training_detail(training_id: int) -> dict[str, Any]:
        """Return the CampusTrain training detail."""
        return await _validated_call(
            client.get_training_detail, _positive_id(training_id, "training_id")
        )

    @server.tool(
        description=(
            "查询培训课程、章节和课时目录。需要当前用户 JWT；training_id 必须是正整数。只读操作。"
        ),
        structured_output=True,
    )
    async def get_training_catalog(training_id: int) -> dict[str, Any]:
        """Return the hierarchical training catalog."""
        return await _validated_call(
            client.get_training_catalog, _positive_id(training_id, "training_id")
        )

    @server.tool(
        description=(
            "查询当前用户报名记录。需要 JWT；page 从 1 开始，size 为 1 到 100，"
            "status 只能是 0、1 或省略。只读操作。"
        ),
        structured_output=True,
    )
    async def get_my_enrollments(
        page: int = 1, size: int = 10, status: int | None = None
    ) -> dict[str, Any]:
        """Return the current user's enrollment page."""
        _page(page, "page", 2_147_483_647)
        _page(size, "size", 100)
        if status not in (None, 0, 1):
            raise ToolError("status 只能是 0、1 或省略")
        return await _validated_call(
            client.get_my_enrollments, page=page, size=size, status=status
        )

    @server.tool(
        description=(
            "查询培训整体学习进度。需要有效学生 JWT 和该培训的有效报名；"
            "training_id 必须是正整数。只读操作。"
        ),
        structured_output=True,
    )
    async def get_training_progress(training_id: int) -> dict[str, Any]:
        """Return training completion progress."""
        return await _validated_call(
            client.get_training_progress, _positive_id(training_id, "training_id")
        )

    @server.tool(
        description=(
            "查询课时学习进度。需要有效学生 JWT 和有效报名；"
            "lesson_id 必须是正整数。只读操作。"
        ),
        structured_output=True,
    )
    async def get_lesson_progress(lesson_id: int) -> dict[str, Any]:
        """Return lesson progress."""
        return await _validated_call(
            client.get_lesson_progress, _positive_id(lesson_id, "lesson_id")
        )

    @server.tool(
        description=(
            "查询章节学习进度。需要有效学生 JWT 和该章节所属培训的有效报名；"
            "chapter_id 必须是正整数。只读操作。"
        ),
        structured_output=True,
    )
    async def get_chapter_progress(chapter_id: int) -> dict[str, Any]:
        """Return chapter progress."""
        return await _validated_call(
            client.get_chapter_progress, _positive_id(chapter_id, "chapter_id")
        )

    return server


async def _validated_call(operation, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        return _success(await operation(*args, **kwargs))
    except CampusClientError as error:
        return _failure(error)
