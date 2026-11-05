"""Async HTTP client for the read-only CampusTrain operations used by the agent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from campus_agent.campus_client.exceptions import (
    CampusBusinessError,
    CampusHttpError,
    CampusTransportError,
    safe_message,
)


class CampusTrainClient:
    """Call CampusTrain through its Gateway using an optional Bearer JWT."""

    def __init__(
        self,
        gateway_url: str,
        jwt_token: str = "",
        *,
        timeout: float | httpx.Timeout = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=gateway_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            trust_env=False,
        )
        self._jwt_token = jwt_token

    async def __aenter__(self) -> CampusTrainClient:
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    def set_jwt(self, token: str) -> None:
        """Replace the in-memory token without persisting it."""
        self._jwt_token = token

    async def login(self, username: str, password: str) -> Mapping[str, Any]:
        """Authenticate and retain the returned JWT only in this client instance."""
        envelope = await self._request(
            "POST", "/auth/login", json={"username": username, "password": password}
        )
        data = self._mapping(envelope)
        token = data.get("token")
        if not isinstance(token, str) or not token:
            raise CampusBusinessError("invalid", "登录响应缺少 token", "/auth/login")
        self.set_jwt(token)
        return data

    async def get_training_detail(self, training_id: int) -> Mapping[str, Any]:
        return self._mapping(await self._request("GET", f"/training/get/{training_id}"))

    async def get_training_catalog(self, training_id: int) -> Mapping[str, Any]:
        return self._mapping(await self._request("GET", f"/training/get/catalog/{training_id}"))

    async def get_my_enrollments(
        self, *, page: int = 1, size: int = 10, status: int | None = None
    ) -> Mapping[str, Any]:
        params: dict[str, int] = {"page": page, "size": size}
        if status is not None:
            params["status"] = status
        return self._mapping(await self._request("GET", "/enrollment/list/mine", params=params))

    async def get_training_progress(self, training_id: int) -> Mapping[str, Any]:
        return self._mapping(
            await self._request("GET", f"/learning/get/training-progress/{training_id}")
        )

    async def get_lesson_progress(self, lesson_id: int) -> Mapping[str, Any]:
        return self._mapping(await self._request("GET", f"/learning/get-progress/{lesson_id}"))

    async def get_chapter_progress(self, chapter_id: int) -> Mapping[str, Any]:
        return self._mapping(
            await self._request("GET", f"/learning/get/chapter-progress/{chapter_id}")
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        if self._jwt_token:
            headers["Authorization"] = f"Bearer {self._jwt_token}"
        try:
            response = await self._client.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as error:
            raise CampusTransportError(
                f"CampusTrain request failed for {path}: {safe_message(error)}"
            ) from error
        if response.status_code >= 400:
            raise CampusHttpError(response.status_code, path, "响应状态异常")
        try:
            envelope = response.json()
        except ValueError as error:
            raise CampusHttpError(response.status_code, path, "响应不是 JSON") from error
        if not isinstance(envelope, Mapping):
            raise CampusHttpError(response.status_code, path, "响应不是对象")
        code = envelope.get("code")
        if code not in (None, 0, 200):
            raise CampusBusinessError(code, str(envelope.get("message", "业务请求失败")), path)
        return envelope.get("data")

    @staticmethod
    def _mapping(data: Any) -> Mapping[str, Any]:
        if not isinstance(data, Mapping):
            raise CampusBusinessError("invalid", "响应 data 不是对象", "response")
        return data
