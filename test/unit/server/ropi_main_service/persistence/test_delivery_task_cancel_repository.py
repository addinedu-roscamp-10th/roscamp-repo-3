import asyncio

from server.ropi_main_service.persistence.repositories.delivery_task_cancel_repository import (
    DeliveryTaskCancelRepository,
)


class FakeAsyncCursor:
    lastrowid = 101


class FakeAsyncTransaction:
    def __init__(self):
        self.cursor = FakeAsyncCursor()
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False


class RecordingAsyncCursor:
    lastrowid = 101

    def __init__(self, row=None):
        self.calls = []
        self.row = row

    async def execute(self, query, params):
        self.calls.append((query, params))

    async def fetchone(self):
        return self.row


def test_async_get_delivery_task_cancel_target_rejects_terminal_task(monkeypatch):
    async def fake_fetch_one(query, params):
        return {
            "task_id": 101,
            "task_status": "COMPLETED",
            "phase": "COMPLETED",
            "assigned_robot_id": "pinky2",
        }

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.delivery_task_cancel_repository.async_fetch_one",
        fake_fetch_one,
    )

    response = asyncio.run(
        DeliveryTaskCancelRepository().async_get_delivery_task_cancel_target("101")
    )

    assert response == {
        "result_code": "REJECTED",
        "result_message": "이미 종료되었거나 취소할 수 없는 운반 task입니다.",
        "reason_code": "TASK_NOT_CANCELLABLE",
        "task_id": 101,
        "task_status": "COMPLETED",
        "assigned_robot_id": "pinky2",
    }


def test_async_get_delivery_task_cancel_target_rejects_missing_task(monkeypatch):
    async def fake_fetch_one(query, params):
        return None

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.delivery_task_cancel_repository.async_fetch_one",
        fake_fetch_one,
    )

    response = asyncio.run(
        DeliveryTaskCancelRepository().async_get_delivery_task_cancel_target("999")
    )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "TASK_NOT_FOUND"
    assert response["task_id"] == 999


def test_async_record_delivery_task_cancel_result_updates_status_history_and_event(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 101,
            "task_status": "RUNNING",
            "phase": "DELIVERY_PICKUP",
            "assigned_robot_id": "pinky2",
        }
    )
    fake_transaction = FakeAsyncTransaction()
    fake_transaction.cursor = cursor

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.delivery_task_cancel_repository.async_transaction",
        lambda: fake_transaction,
    )

    response = asyncio.run(
        DeliveryTaskCancelRepository().async_record_delivery_task_cancel_result(
            task_id="101",
            cancel_response={
                "result_code": "CANCEL_REQUESTED",
                "result_message": "action cancel request was accepted.",
                "cancel_requested": True,
            },
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert response["task_status"] == "CANCEL_REQUESTED"
    assert response["assigned_robot_id"] == "pinky2"
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
    assert cursor.calls[1][1][0:3] == (
        "USER_CANCEL_REQUESTED",
        "CANCEL_REQUESTED",
        "action cancel request was accepted.",
    )


def test_async_record_delivery_task_cancel_result_logs_rejection_without_status_update(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 101,
            "task_status": "RUNNING",
            "phase": "DELIVERY_PICKUP",
            "assigned_robot_id": "pinky2",
        }
    )
    fake_transaction = FakeAsyncTransaction()
    fake_transaction.cursor = cursor

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.delivery_task_cancel_repository.async_transaction",
        lambda: fake_transaction,
    )

    response = asyncio.run(
        DeliveryTaskCancelRepository().async_record_delivery_task_cancel_result(
            task_id="101",
            cancel_response={
                "result_code": "NOT_FOUND",
                "result_message": "matching active action goal was not found.",
                "cancel_requested": False,
            },
        )
    )

    assert response["result_code"] == "NOT_FOUND"
    assert response["task_status"] == "RUNNING"
    assert [call[0].split()[0] for call in cursor.calls] == [
        "SELECT",
        "INSERT",
    ]
    assert "INSERT INTO task_event_log" in cursor.calls[1][0]
    assert cursor.calls[1][1][1:4] == (
        "DELIVERY_TASK_CANCEL_REJECTED",
        "WARNING",
        "pinky2",
    )


def test_async_record_delivery_task_cancelled_result_finalizes_cancel_requested_task(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 101,
            "task_status": "CANCEL_REQUESTED",
            "phase": "CANCEL_REQUESTED",
            "assigned_robot_id": "pinky2",
        }
    )
    fake_transaction = FakeAsyncTransaction()
    fake_transaction.cursor = cursor

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.delivery_task_cancel_repository.async_transaction",
        lambda: fake_transaction,
    )

    workflow_response = {
        "result_code": "FAILED",
        "result_message": "goal canceled by user request.",
        "status": 5,
    }
    response = asyncio.run(
        DeliveryTaskCancelRepository().async_record_delivery_task_cancelled_result(
            task_id="101",
            workflow_response=workflow_response,
        )
    )

    assert response["result_code"] == "CANCELLED"
    assert response["reason_code"] == "ROS_ACTION_CANCELLED"
    assert response["task_status"] == "CANCELLED"
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
    assert cursor.calls[1][1][0:3] == (
        "ROS_ACTION_CANCELLED",
        "CANCELLED",
        "goal canceled by user request.",
    )
    assert cursor.calls[3][1][1:7] == (
        "DELIVERY_TASK_CANCELLED",
        "INFO",
        "pinky2",
        "CANCELLED",
        "ROS_ACTION_CANCELLED",
        "goal canceled by user request.",
    )
