import httpx
import pytest

from campus_agent.campus_client import CampusTrainClient
from campus_agent.campus_client.exceptions import CampusBusinessError, CampusHttpError


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
