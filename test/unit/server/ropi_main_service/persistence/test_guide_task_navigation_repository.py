import asyncio

from server.ropi_main_service.persistence.repositories.guide_task_navigation_repository import (
    GuideTaskNavigationRepository,
)


class FakeSyncCursor:
    def __init__(self, row=None):
        self.calls = []
        self._row = row if row is not None else {
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": "pinky1",
            "destination_goal_pose_id": "delivery_room_301",
            "pose_x": 1.5,
            "pose_y": 2.5,
            "pose_yaw": 0.25,
            "frame_id": "map",
        }

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return self._row


class FakeAsyncCursor:
    def __init__(self, row=None):
        self.calls = []
        self._row = row if row is not None else {
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": "pinky1",
            "destination_goal_pose_id": "delivery_room_301",
            "pose_x": 1.5,
            "pose_y": 2.5,
            "pose_yaw": 0.25,
            "frame_id": "map",
        }

    async def execute(self, query, params=None):
        self.calls.append((query, params))

    async def fetchone(self):
        return self._row


def test_get_guide_driving_context_returns_destination_pose_stamped():
    cursor = FakeSyncCursor()
    repository = GuideTaskNavigationRepository(fetch_one_func=lambda query, params: cursor.fetchone())

    response = repository.get_guide_driving_context(task_id=3001)

    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 3001
    assert response["assigned_robot_id"] == "pinky1"
    assert response["destination_id"] == "delivery_room_301"
    assert response["goal_pose"]["header"]["frame_id"] == "map"
    assert response["goal_pose"]["pose"]["position"]["x"] == 1.5


def test_get_guide_driving_context_rejects_unknown_task():
    repository = GuideTaskNavigationRepository(fetch_one_func=lambda query, params: None)

    response = repository.get_guide_driving_context(task_id=9999)

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "TASK_NOT_FOUND"


def test_get_guide_driving_context_rejects_task_before_tracking_wait():
    row = {
        "task_id": 3001,
        "task_type": "GUIDE",
        "task_status": "WAITING_DISPATCH",
        "phase": "WAIT_GUIDE_START_CONFIRM",
        "assigned_robot_id": "pinky1",
        "destination_goal_pose_id": "delivery_room_301",
        "pose_x": 1.5,
        "pose_y": 2.5,
        "pose_yaw": 0.25,
        "frame_id": "map",
    }
    repository = GuideTaskNavigationRepository(fetch_one_func=lambda query, params: row)

    response = repository.get_guide_driving_context(task_id=3001)

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "GUIDE_STATE_MISMATCH"


def test_async_get_guide_driving_context_uses_async_fetch():
    async def fake_fetch_one(query, params):
        return {
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": "pinky1",
            "destination_goal_pose_id": "delivery_room_301",
            "pose_x": 1.5,
            "pose_y": 2.5,
            "pose_yaw": 0.25,
            "frame_id": "map",
        }

    repository = GuideTaskNavigationRepository(async_fetch_one_func=fake_fetch_one)

    response = asyncio.run(repository.async_get_guide_driving_context(task_id=3001))

    assert response["result_code"] == "ACCEPTED"
    assert response["goal_pose"]["pose"]["position"]["y"] == 2.5
