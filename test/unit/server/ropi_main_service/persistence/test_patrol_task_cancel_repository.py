import asyncio

from server.ropi_main_service.persistence.repositories.patrol_task_cancel_repository import (
    PatrolTaskCancelRepository,
)


class FakeAsyncTransaction:
    def __init__(self, cursor):
        self.cursor = cursor

    async def __aenter__(self):
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        return False


class RecordingAsyncCursor:
    def __init__(self, row=None):
        self.calls = []
        self.row = row

    async def execute(self, query, params):
        self.calls.append((query, params))

    async def fetchone(self):
        return self.row


def test_async_record_patrol_task_cancel_result_updates_task_detail_and_event(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "FOLLOW_PATROL_PATH",
            "assigned_robot_id": "pinky3",
            "patrol_status": "RUNNING",
        }
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_cancel_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    response = asyncio.run(
        PatrolTaskCancelRepository().async_record_patrol_task_cancel_result(
            task_id="2001",
            caregiver_id=7,
            reason="operator_cancel",
            cancel_response={
                "result_code": "CANCEL_REQUESTED",
                "result_message": "action cancel request was accepted.",
                "task_id": "2001",
                "cancel_requested": True,
            },
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert response["task_type"] == "PATROL"
    assert response["task_status"] == "CANCEL_REQUESTED"
    assert response["reason_code"] == "USER_CANCEL_REQUESTED"
    assert response["cancel_requested"] is True
    assert [call[0].split()[0] for call in cursor.calls] == [
        "SELECT",
        "UPDATE",
        "UPDATE",
        "INSERT",
        "INSERT",
    ]
    assert "FOR UPDATE" in cursor.calls[0][0]
    assert "UPDATE task" in cursor.calls[1][0]
    assert "UPDATE patrol_task_detail" in cursor.calls[2][0]
    assert "INSERT INTO task_state_history" in cursor.calls[3][0]
    assert "INSERT INTO task_event_log" in cursor.calls[4][0]
    assert cursor.calls[2][1] == ("CANCEL_REQUESTED", 2001)
    assert cursor.calls[4][1][1:7] == (
        "PATROL_TASK_CANCEL_REQUESTED",
        "INFO",
        "pinky3",
        "CANCEL_REQUESTED",
        "USER_CANCEL_REQUESTED",
        "action cancel request was accepted.",
    )


def test_async_record_patrol_task_cancel_result_normalizes_successful_ros_result(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "FOLLOW_PATROL_PATH",
            "assigned_robot_id": "pinky3",
            "patrol_status": "RUNNING",
        }
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_cancel_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    response = asyncio.run(
        PatrolTaskCancelRepository().async_record_patrol_task_cancel_result(
            task_id="2001",
            caregiver_id=7,
            reason="operator_cancel",
            cancel_response={
                "result_code": "SUCCESS",
                "result_message": "done",
                "task_id": "2001",
                "cancel_requested": True,
            },
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert response["task_status"] == "CANCEL_REQUESTED"
    assert response["cancel_requested"] is True
    assert cursor.calls[1][1][1:3] == ("CANCEL_REQUESTED", "done")
    assert cursor.calls[4][1][4] == "CANCEL_REQUESTED"


def test_async_record_patrol_task_cancel_result_keeps_status_when_ros_rejects(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "FOLLOW_PATROL_PATH",
            "assigned_robot_id": "pinky3",
            "patrol_status": "RUNNING",
        }
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_cancel_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    response = asyncio.run(
        PatrolTaskCancelRepository().async_record_patrol_task_cancel_result(
            task_id="2001",
            caregiver_id=7,
            reason="operator_cancel",
            cancel_response={
                "result_code": "NOT_FOUND",
                "result_message": "matching active action goal was not found.",
                "task_id": "2001",
                "cancel_requested": False,
            },
        )
    )

    assert response["result_code"] == "NOT_FOUND"
    assert response["task_status"] == "RUNNING"
    assert response["cancel_requested"] is False
    assert [call[0].split()[0] for call in cursor.calls] == ["SELECT", "INSERT"]
    assert cursor.calls[1][1][1:3] == ("PATROL_TASK_CANCEL_REJECTED", "WARNING")
