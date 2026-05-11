import asyncio

from server.ropi_main_service.persistence.repositories.delivery_task_execution_repository import (
    DeliveryTaskExecutionRepository,
)


class RecordingAsyncCursor:
    def __init__(self, row=None):
        self.calls = []
        self.row = row

    async def execute(self, query, params):
        self.calls.append((query, params))

    async def fetchone(self):
        return self.row


class FakeAsyncTransaction:
    def __init__(self, row=None):
        self.cursor = RecordingAsyncCursor(row=row)

    async def __aenter__(self):
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_async_record_delivery_execution_started_marks_task_running(monkeypatch):
    row = {
        "task_id": 101,
        "task_status": "WAITING_DISPATCH",
        "phase": "REQUESTED",
        "assigned_robot_id": "pinky2",
    }
    transaction = FakeAsyncTransaction(row=row)
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.delivery_task_execution_repository.async_transaction",
        lambda: transaction,
    )

    response = asyncio.run(
        DeliveryTaskExecutionRepository().async_record_delivery_execution_started(101)
    )

    assert response == {
        "result_code": "ACCEPTED",
        "result_message": "운반 경로 실행을 시작했습니다.",
        "reason_code": None,
        "task_id": 101,
        "task_status": "RUNNING",
        "phase": "DELIVERY_PICKUP",
        "assigned_robot_id": "pinky2",
        "cancellable": True,
    }
    assert [call[0].split()[0] for call in transaction.cursor.calls] == [
        "SELECT",
        "UPDATE",
        "INSERT",
        "INSERT",
    ]
    assert "FOR UPDATE" in transaction.cursor.calls[0][0]
    assert "UPDATE task" in transaction.cursor.calls[1][0]
    assert "INSERT INTO task_state_history" in transaction.cursor.calls[2][0]
    assert "INSERT INTO task_event_log" in transaction.cursor.calls[3][0]
    assert transaction.cursor.calls[1][1] == (
        "ACCEPTED",
        "운반 경로 실행을 시작했습니다.",
        101,
    )


def test_async_record_delivery_execution_started_rejects_terminal_task(monkeypatch):
    row = {
        "task_id": 101,
        "task_status": "FAILED",
        "phase": "FAILED",
        "assigned_robot_id": "pinky2",
    }
    transaction = FakeAsyncTransaction(row=row)
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.delivery_task_execution_repository.async_transaction",
        lambda: transaction,
    )

    response = asyncio.run(
        DeliveryTaskExecutionRepository().async_record_delivery_execution_started(101)
    )

    assert response["result_code"] == "NOT_ALLOWED"
    assert response["reason_code"] == "DELIVERY_TASK_ALREADY_TERMINAL"
    assert [call[0].split()[0] for call in transaction.cursor.calls] == ["SELECT"]
