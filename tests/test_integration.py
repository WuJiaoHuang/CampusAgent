import os

import pytest

from campus_agent.campus_client import CampusTrainClient

pytestmark = pytest.mark.integration


@pytest.mark.anyio
async def test_real_campustrain_read_paths():
    gateway = os.getenv("CAMPUS_AGENT_INTEGRATION_GATEWAY")
    username = os.getenv("CAMPUS_AGENT_INTEGRATION_USERNAME")
    password = os.getenv("CAMPUS_AGENT_INTEGRATION_PASSWORD")
    training_id = int(os.getenv("CAMPUS_AGENT_INTEGRATION_TRAINING_ID", "16001"))
    lesson_id = int(os.getenv("CAMPUS_AGENT_INTEGRATION_LESSON_ID", "16001"))
    if not all((gateway, username, password)):
        pytest.skip("未提供 CAMPUS_AGENT_INTEGRATION_*，不伪造真实联调结果")
    async with CampusTrainClient(gateway, timeout=20) as client:
        await client.login(username, password)
        detail = await client.get_training_detail(training_id)
        catalog = await client.get_training_catalog(training_id)
        enrollments = await client.get_my_enrollments()
        progress = await client.get_training_progress(training_id)
        lesson_progress = await client.get_lesson_progress(lesson_id)
    assert isinstance(detail["id"], int)
    assert isinstance(detail["title"], str)
    assert isinstance(catalog["trainingId"], int)
    assert isinstance(catalog["courses"], list)
    assert isinstance(enrollments["records"], list)
    assert isinstance(enrollments["total"], int)
    assert isinstance(progress["totalLessons"], int)
    assert isinstance(progress["completedLessons"], int)
    assert isinstance(progress["progressRatio"], (int, float))
    assert isinstance(lesson_progress["lessonId"], int)
    assert isinstance(lesson_progress["progressSeconds"], (int, float))
