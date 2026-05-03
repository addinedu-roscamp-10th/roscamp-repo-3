import asyncio

from server.ropi_main_service.persistence.repositories.guide_tracking_repository import (
    GuideTrackingRepository,
)


def test_get_active_guide_task_for_robot_filters_non_terminal_guide_task():
    queries = []
    row = {
        "task_id": 3001,
        "assigned_robot_id": "pinky1",
        "task_status": "RUNNING",
        "phase": "GUIDANCE_RUNNING",
        "guide_phase": "GUIDANCE_RUNNING",
        "target_track_id": "track_17",
    }

    def fake_fetch_one(query, params):
        queries.append((query, params))
        return row

    repository = GuideTrackingRepository(fetch_one_func=fake_fetch_one)

    response = repository.get_active_guide_task_for_robot("pinky1")

    assert response == row
    assert queries[0][1] == ("pinky1",)
    assert "guide_task_detail" in queries[0][0]
    assert "target_track_id IS NOT NULL" in queries[0][0]


def test_async_get_active_guide_task_for_robot_uses_async_fetch_one():
    async def fake_fetch_one(query, params):
        return {
            "task_id": 3001,
            "assigned_robot_id": params[0],
            "task_status": "RUNNING",
            "phase": "GUIDANCE_RUNNING",
            "guide_phase": "GUIDANCE_RUNNING",
            "target_track_id": "track_17",
        }

    repository = GuideTrackingRepository(async_fetch_one_func=fake_fetch_one)

    async def scenario():
        return await repository.async_get_active_guide_task_for_robot("pinky1")

    response = asyncio.run(scenario())

    assert response["assigned_robot_id"] == "pinky1"
    assert response["target_track_id"] == "track_17"
