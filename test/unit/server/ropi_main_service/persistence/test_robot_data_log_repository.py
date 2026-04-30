import asyncio
import json

from server.ropi_main_service.persistence.repositories.robot_data_log_repository import (
    RobotDataLogRepository,
)


def build_sample(*, robot_id="pinky2", task_id=101):
    return {
        "robot_id": robot_id,
        "task_id": task_id,
        "data_type": "NAVIGATION_FEEDBACK",
        "pose_x": 1.2,
        "pose_y": 0.8,
        "pose_yaw": 0.0,
        "battery_percent": None,
        "payload": {"feedback_type": "NAVIGATION_FEEDBACK"},
    }


def test_async_insert_feedback_samples_uses_bulk_execute(monkeypatch):
    calls = []

    async def fake_async_execute_many(query, params_seq):
        calls.append((query, params_seq))
        return len(params_seq)

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.robot_data_log_repository.async_execute_many",
        fake_async_execute_many,
    )

    asyncio.run(
        RobotDataLogRepository().async_insert_feedback_samples(
            [
                build_sample(),
                build_sample(robot_id="jetcobot1", task_id=102),
            ]
        )
    )

    assert "INSERT INTO robot_data_log" in calls[0][0]
    assert calls[0][1] == [
        (
            "pinky2",
            101,
            "NAVIGATION_FEEDBACK",
            1.2,
            0.8,
            0.0,
            None,
            json.dumps({"feedback_type": "NAVIGATION_FEEDBACK"}, ensure_ascii=False),
        ),
        (
            "jetcobot1",
            102,
            "NAVIGATION_FEEDBACK",
            1.2,
            0.8,
            0.0,
            None,
            json.dumps({"feedback_type": "NAVIGATION_FEEDBACK"}, ensure_ascii=False),
        ),
    ]
