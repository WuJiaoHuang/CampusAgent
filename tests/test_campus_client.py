import json

import httpx
import pytest

from campus_agent.campus_client import CampusTrainClient
from campus_agent.campus_client.exceptions import (
    CampusBusinessError,
    CampusHttpError,
    CampusTransportError,
)


class FakeTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(
                200, json={"code": 0, "message": "成功", "data": {"token": "test-token"}}
            )
        assert request.headers["authorization"] == "Bearer test-token"
        if request.url.path == "/training/get/1":
            return httpx.Response(200, json={"code": 0, "data": {"id": 1, "name": "demo"}})
        if request.url.path == "/training/get/catalog/1":
            return httpx.Response(200, json={"code": 0, "data": {"courses": []}})
        if request.url.path == "/enrollment/list/mine":
            return httpx.Response(200, json={"code": 0, "data": {"records": [], "total": 0}})
        if request.url.path == "/enrollment/create":
            assert json.loads(request.content) == {"trainingId": 1}
            return httpx.Response(200, json={"code": 0, "data": 9001})
        if request.url.path == "/enrollment/cancel/9001":
            return httpx.Response(200, json={"code": 0, "data": None})
        if request.url.path == "/learning/get/training-progress/1":
            return httpx.Response(200, json={"code": 0, "data": {"progressRatio": 0}})
        if request.url.path == "/learning/get-progress/1":
            return httpx.Response(200, json={"code": 0, "data": {"lessonId": 1}})
        if request.url.path == "/learning/get/chapter-progress/1":
            return httpx.Response(200, json={"code": 0, "data": {"chapterId": 1}})
        return httpx.Response(404, json={"message": "missing"})


@pytest.mark.anyio
async def test_client_login_and_read_operations():
    async with CampusTrainClient("http://gateway", transport=FakeTransport()) as client:
        await client.login("student", "password")
        assert (await client.get_training_detail(1))["id"] == 1
        assert (await client.get_training_catalog(1))["courses"] == []
        assert (await client.get_my_enrollments())["total"] == 0
        assert (await client.get_training_progress(1))["progressRatio"] == 0
        assert (await client.get_lesson_progress(1))["lessonId"] == 1
        assert (await client.get_chapter_progress(1))["chapterId"] == 1
        assert await client.create_enrollment(1) == 9001
        await client.cancel_enrollment(9001)


@pytest.mark.anyio
async def test_client_maps_http_and_business_errors():
    class ErrorTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if request.url.path == "/http":
                return httpx.Response(503, text="unavailable")
            return httpx.Response(200, json={"code": 400, "message": "bad request", "data": None})

    async with CampusTrainClient("http://gateway", transport=ErrorTransport()) as client:
        with pytest.raises(CampusHttpError):
            await client._request("GET", "/http")
        with pytest.raises(CampusBusinessError):
            await client._request("GET", "/business")


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [401, 429, 503])
async def test_client_maps_auth_throttling_and_unavailable_statuses(status_code):
    class StatusTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(
                status_code,
                text='{"password":"secret-password","token":"secret-jwt"}',
            )

    async with CampusTrainClient("http://gateway", transport=StatusTransport()) as client:
        with pytest.raises(CampusHttpError) as caught:
            await client._request("GET", "/sensitive")
    assert caught.value.status_code == status_code
    assert "secret-password" not in str(caught.value)
    assert "secret-jwt" not in str(caught.value)


@pytest.mark.anyio
async def test_client_maps_invalid_json():
    class InvalidJsonTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, text="not-json")

    async with CampusTrainClient("http://gateway", transport=InvalidJsonTransport()) as client:
        with pytest.raises(CampusHttpError, match="响应不是 JSON"):
            await client._request("GET", "/invalid-json")


@pytest.mark.anyio
async def test_client_maps_connection_failure_without_secret_text():
    class ConnectionTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise httpx.ConnectError("connection failed with token=secret-jwt", request=request)

    async with CampusTrainClient("http://gateway", transport=ConnectionTransport()) as client:
        with pytest.raises(CampusTransportError) as caught:
            await client._request("GET", "/connect")
    assert "secret-jwt" not in str(caught.value)


@pytest.mark.anyio
async def test_client_maps_timeout_without_secret_text():
    class TimeoutTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            raise httpx.ReadTimeout("password=secret-password", request=request)

    async with CampusTrainClient("http://gateway", transport=TimeoutTransport()) as client:
        with pytest.raises(CampusTransportError) as caught:
            await client._request("GET", "/timeout")
    assert "secret-password" not in str(caught.value)
