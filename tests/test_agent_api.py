from fastapi.testclient import TestClient

from campus_agent.api import app


def test_chat_requires_jwt():
    response = TestClient(app).post("/agent/chat", json={"message": "你好", "session_id": "s1"})
    assert response.status_code == 401


def test_chat_is_user_scoped():
    from campus_agent.api import service
    service.jwt_decoder = lambda token: {"sub": token}
    client = TestClient(app)
    payload = {"message": "你好", "session_id": "same"}
    first = client.post("/agent/chat", json=payload, headers={"Authorization": "Bearer a"})
    second = client.post("/agent/chat", json=payload, headers={"Authorization": "Bearer b"})
    assert first.status_code == second.status_code == 200
    assert first.json()["session_id"] == "same"
