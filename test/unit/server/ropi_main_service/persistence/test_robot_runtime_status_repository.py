import asyncio

from server.ropi_main_service.persistence.repositories.robot_runtime_status_repository import (
    RobotRuntimeStatusRepository,
)


def test_async_upsert_runtime_status_uses_robot_runtime_status_schema(monkeypatch):
    calls = []

    async def fake_async_execute(query, params):
        calls.append((query, params))
        return 1

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.robot_runtime_status_repository.async_execute",
        fake_async_execute,
    )

    asyncio.run(
        RobotRuntimeStatusRepository().async_upsert_runtime_status(
            robot_id="pinky2",
            robot_kind="PINKY",
            runtime_state="RUNNING",
            active_task_id=101,
            battery_percent=87.5,
            pose_x=1.2,
            pose_y=0.8,
            pose_yaw=0.0,
            frame_id="map",
            fault_code=None,
        )
    )

    assert "INSERT INTO robot_runtime_status" in calls[0][0]
    assert "ON DUPLICATE KEY UPDATE" in calls[0][0]
    assert calls[0][1] == (
        "pinky2",
        "PINKY",
        "RUNNING",
        101,
        87.5,
        1.2,
        0.8,
        0.0,
        "map",
        None,
    )


def test_async_upsert_runtime_statuses_uses_bulk_execute(monkeypatch):
    calls = []

    async def fake_async_execute_many(query, params_seq):
        calls.append((query, params_seq))
        return len(params_seq)

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.robot_runtime_status_repository.async_execute_many",
        fake_async_execute_many,
    )

    asyncio.run(
        RobotRuntimeStatusRepository().async_upsert_runtime_statuses(
            [
                {
                    "robot_id": "pinky2",
                    "robot_kind": "PINKY",
                    "runtime_state": "RUNNING",
                    "active_task_id": 101,
                    "battery_percent": None,
                    "pose_x": 1.2,
                    "pose_y": 0.8,
                    "pose_yaw": 0.0,
                    "frame_id": "map",
                    "fault_code": None,
                },
                {
                    "robot_id": "jetcobot1",
                    "robot_kind": "JETCOBOT",
                    "runtime_state": "RUNNING",
                    "active_task_id": 101,
                    "battery_percent": None,
                    "pose_x": None,
                    "pose_y": None,
                    "pose_yaw": None,
                    "frame_id": None,
                    "fault_code": None,
                },
            ]
        )
    )

    assert "INSERT INTO robot_runtime_status" in calls[0][0]
    assert calls[0][1] == [
        ("pinky2", "PINKY", "RUNNING", 101, None, 1.2, 0.8, 0.0, "map", None),
        ("jetcobot1", "JETCOBOT", "RUNNING", 101, None, None, None, None, None, None),
    ]
