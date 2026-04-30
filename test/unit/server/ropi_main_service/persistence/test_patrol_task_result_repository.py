import asyncio

from server.ropi_main_service.persistence.repositories.patrol_task_result_repository import (
    PatrolTaskResultRepository,
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


def test_async_record_patrol_task_workflow_result_finalizes_success(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "PATROL_PATH_EXECUTION",
            "assigned_robot_id": "pinky3",
            "patrol_status": "RUNNING",
            "waypoint_count": 3,
        }
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_result_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    workflow_response = {
        "result_code": "SUCCEEDED",
        "result_message": "patrol completed",
        "completed_waypoint_count": 3,
    }
    response = asyncio.run(
        PatrolTaskResultRepository().async_record_patrol_task_workflow_result(
            task_id="2001",
            workflow_response=workflow_response,
        )
    )

    assert response["result_code"] == "SUCCEEDED"
    assert response["task_status"] == "COMPLETED"
    assert response["assigned_robot_id"] == "pinky3"
    assert response["workflow_result"] == workflow_response
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
    assert cursor.calls[1][1][0:5] == (
        "COMPLETED",
        "COMPLETED",
        None,
        "SUCCEEDED",
        "patrol completed",
    )
    assert cursor.calls[2][1] == ("COMPLETED", 2, 2001)
    assert cursor.calls[4][1][1:7] == (
        "PATROL_TASK_COMPLETED",
        "INFO",
        "pinky3",
        "SUCCEEDED",
        None,
        "patrol completed",
    )


def test_async_record_patrol_task_workflow_result_normalizes_legacy_success(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "PATROL_PATH_EXECUTION",
            "assigned_robot_id": "pinky3",
            "patrol_status": "RUNNING",
            "waypoint_count": 3,
        }
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_result_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    response = asyncio.run(
        PatrolTaskResultRepository().async_record_patrol_task_workflow_result(
            task_id="2001",
            workflow_response={"result_code": "SUCCESS"},
        )
    )

    assert response["result_code"] == "SUCCEEDED"
    assert response["task_status"] == "COMPLETED"
    assert cursor.calls[1][1][3] == "SUCCEEDED"


def test_async_record_patrol_task_workflow_result_finalizes_failure(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "PATROL_PATH_EXECUTION",
            "assigned_robot_id": "pinky3",
            "patrol_status": "RUNNING",
            "waypoint_count": 3,
        }
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_result_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    workflow_response = {
        "result_code": "FAILED",
        "result_message": "patrol waypoint 2 failed.",
        "reason_code": "PATROL_PATH_ACTION_FAILED",
        "completed_waypoint_count": 1,
    }
    response = asyncio.run(
        PatrolTaskResultRepository().async_record_patrol_task_workflow_result(
            task_id="2001",
            workflow_response=workflow_response,
        )
    )

    assert response["result_code"] == "FAILED"
    assert response["reason_code"] == "PATROL_PATH_ACTION_FAILED"
    assert response["task_status"] == "FAILED"
    assert cursor.calls[1][1][0:5] == (
        "FAILED",
        "FAILED",
        "PATROL_PATH_ACTION_FAILED",
        "FAILED",
        "patrol waypoint 2 failed.",
    )
    assert cursor.calls[2][1] == ("FAILED", 0, 2001)
    assert cursor.calls[4][1][1:7] == (
        "PATROL_TASK_FAILED",
        "ERROR",
        "pinky3",
        "FAILED",
        "PATROL_PATH_ACTION_FAILED",
        "patrol waypoint 2 failed.",
    )


def test_async_record_patrol_task_workflow_result_ignores_terminal_task(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 2001,
            "task_status": "COMPLETED",
            "phase": "COMPLETED",
            "assigned_robot_id": "pinky3",
            "patrol_status": "COMPLETED",
            "waypoint_count": 3,
        }
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_result_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    response = asyncio.run(
        PatrolTaskResultRepository().async_record_patrol_task_workflow_result(
            task_id="2001",
            workflow_response={"result_code": "SUCCEEDED"},
        )
    )

    assert response["result_code"] == "IGNORED"
    assert response["reason_code"] == "TASK_ALREADY_TERMINAL"
    assert response["task_status"] == "COMPLETED"
    assert [call[0].split()[0] for call in cursor.calls] == ["SELECT"]
