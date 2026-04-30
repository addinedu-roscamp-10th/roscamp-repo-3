import asyncio
import json

from server.ropi_main_service.persistence.repositories.command_execution_repository import (
    CommandExecutionRepository,
)


class FakeAsyncTransaction:
    def __init__(self, cursor):
        self.cursor = cursor

    async def __aenter__(self):
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        return False


class RecordingAsyncCursor:
    def __init__(self):
        self.calls = []
        self.lastrowid = 501

    async def execute(self, query, params):
        self.calls.append((query, params))


def test_async_start_command_execution_inserts_command_snapshot(monkeypatch):
    cursor = RecordingAsyncCursor()

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.command_execution_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    execution_id = asyncio.run(
        CommandExecutionRepository().async_start_command_execution(
            task_id="101",
            transport="ROS_ACTION",
            command_type="NAVIGATE_TO_GOAL",
            command_phase="DELIVERY_PICKUP",
            target_component="ros_service",
            target_robot_id="pinky2",
            target_endpoint="/ropi/control/pinky2/navigate_to_goal",
            request_payload={"goal": {"task_id": "101"}},
        )
    )

    assert execution_id == 501
    assert "INSERT INTO command_execution" in cursor.calls[0][0]
    assert cursor.calls[0][1][0:7] == (
        101,
        "ROS_ACTION",
        "NAVIGATE_TO_GOAL",
        "DELIVERY_PICKUP",
        "ros_service",
        "pinky2",
        "/ropi/control/pinky2/navigate_to_goal",
    )
    assert json.loads(cursor.calls[0][1][7]) == {"goal": {"task_id": "101"}}


def test_async_finish_command_execution_updates_result_snapshot(monkeypatch):
    calls = []

    async def fake_async_execute(query, params):
        calls.append((query, params))
        return 1

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.command_execution_repository.async_execute",
        fake_async_execute,
    )

    asyncio.run(
        CommandExecutionRepository().async_finish_command_execution(
            command_execution_id=501,
            accepted=True,
            result_code="SUCCESS",
            result_message="navigation done",
            response_payload={"accepted": True, "result_code": "SUCCESS"},
        )
    )

    assert "UPDATE command_execution" in calls[0][0]
    assert calls[0][1][0:4] == (
        True,
        "SUCCESS",
        "navigation done",
        json.dumps({"accepted": True, "result_code": "SUCCESS"}, ensure_ascii=False),
    )
    assert calls[0][1][4] == 501
