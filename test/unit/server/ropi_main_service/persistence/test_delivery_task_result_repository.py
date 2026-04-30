import asyncio

from server.ropi_main_service.persistence.repositories.delivery_task_result_repository import (
    DeliveryTaskResultRepository,
)


class FakeAsyncTransaction:
    def __init__(self, cursor):
        self.cursor = cursor
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False


class RecordingAsyncCursor:
    def __init__(self, row=None):
        self.calls = []
        self.row = row

    async def execute(self, query, params):
        self.calls.append((query, params))

    async def fetchone(self):
        return self.row


def test_async_record_delivery_task_workflow_result_finalizes_success(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 101,
            "task_status": "RUNNING",
            "phase": "RETURN_TO_DOCK",
            "assigned_robot_id": "pinky2",
        }
    )
    fake_transaction = FakeAsyncTransaction(cursor)

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.delivery_task_result_repository.async_transaction",
        lambda: fake_transaction,
    )

    workflow_response = {
        "result_code": "SUCCESS",
        "result_message": "return to dock complete.",
    }
    response = asyncio.run(
        DeliveryTaskResultRepository().async_record_delivery_task_workflow_result(
            task_id="101",
            workflow_response=workflow_response,
        )
    )

    assert response["result_code"] == "SUCCESS"
    assert response["task_status"] == "COMPLETED"
    assert response["assigned_robot_id"] == "pinky2"
    assert response["workflow_result"] == workflow_response
    assert [call[0].split()[0] for call in cursor.calls] == [
        "SELECT",
        "UPDATE",
        "INSERT",
        "INSERT",
    ]
    assert "FOR UPDATE" in cursor.calls[0][0]
    assert "UPDATE task" in cursor.calls[1][0]
    assert "INSERT INTO task_state_history" in cursor.calls[2][0]
    assert "INSERT INTO task_event_log" in cursor.calls[3][0]
    assert cursor.calls[1][1][0:5] == (
        "COMPLETED",
        "COMPLETED",
        None,
        "SUCCESS",
        "return to dock complete.",
    )
    assert cursor.calls[3][1][1:7] == (
        "DELIVERY_TASK_COMPLETED",
        "INFO",
        "pinky2",
        "SUCCESS",
        None,
        "return to dock complete.",
    )


def test_async_record_delivery_task_workflow_result_finalizes_failure(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 101,
            "task_status": "RUNNING",
            "phase": "DELIVERY_DESTINATION",
            "assigned_robot_id": "pinky2",
        }
    )
    fake_transaction = FakeAsyncTransaction(cursor)

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.delivery_task_result_repository.async_transaction",
        lambda: fake_transaction,
    )

    workflow_response = {
        "result_code": "FAILED",
        "result_message": "destination navigation failed.",
        "reason_code": "NAVIGATION_TIMEOUT",
    }
    response = asyncio.run(
        DeliveryTaskResultRepository().async_record_delivery_task_workflow_result(
            task_id="101",
            workflow_response=workflow_response,
        )
    )

    assert response["result_code"] == "FAILED"
    assert response["reason_code"] == "NAVIGATION_TIMEOUT"
    assert response["task_status"] == "FAILED"
    assert [call[0].split()[0] for call in cursor.calls] == [
        "SELECT",
        "UPDATE",
        "INSERT",
        "INSERT",
    ]
    assert cursor.calls[1][1][0:5] == (
        "FAILED",
        "FAILED",
        "NAVIGATION_TIMEOUT",
        "FAILED",
        "destination navigation failed.",
    )
    assert cursor.calls[3][1][1:7] == (
        "DELIVERY_TASK_FAILED",
        "ERROR",
        "pinky2",
        "FAILED",
        "NAVIGATION_TIMEOUT",
        "destination navigation failed.",
    )


def test_async_record_delivery_task_workflow_result_ignores_terminal_task(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 101,
            "task_status": "COMPLETED",
            "phase": "COMPLETED",
            "assigned_robot_id": "pinky2",
        }
    )
    fake_transaction = FakeAsyncTransaction(cursor)

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.delivery_task_result_repository.async_transaction",
        lambda: fake_transaction,
    )

    response = asyncio.run(
        DeliveryTaskResultRepository().async_record_delivery_task_workflow_result(
            task_id="101",
            workflow_response={"result_code": "SUCCESS"},
        )
    )

    assert response["result_code"] == "IGNORED"
    assert response["reason_code"] == "TASK_ALREADY_TERMINAL"
    assert response["task_status"] == "COMPLETED"
    assert [call[0].split()[0] for call in cursor.calls] == ["SELECT"]
