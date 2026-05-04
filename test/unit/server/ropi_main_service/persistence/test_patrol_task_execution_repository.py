import asyncio

from server.ropi_main_service.persistence.repositories.patrol_task_execution_repository import (
    PatrolTaskExecutionRepository,
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


def test_async_get_patrol_execution_snapshot_loads_task_path(monkeypatch):
    row = {
        "task_id": 2001,
        "assigned_robot_id": "pinky3",
        "frame_id": "map",
        "waypoint_count": 2,
        "path_snapshot_json": '{"header":{"frame_id":"map"},"poses":[{},{}]}',
    }
    transaction = FakeAsyncTransaction(row=row)
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_execution_repository.async_transaction",
        lambda: transaction,
    )

    snapshot = asyncio.run(
        PatrolTaskExecutionRepository().async_get_patrol_execution_snapshot(2001)
    )

    assert snapshot == {
        "task_id": 2001,
        "assigned_robot_id": "pinky3",
        "frame_id": "map",
        "waypoint_count": 2,
        "path_snapshot_json": {
            "header": {"frame_id": "map"},
            "poses": [{}, {}],
        },
    }
    assert "FROM task t" in transaction.cursor.calls[0][0]
    assert transaction.cursor.calls[0][1] == (2001,)


def test_async_get_patrol_execution_snapshot_rejects_missing_task(monkeypatch):
    transaction = FakeAsyncTransaction(row=None)
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_execution_repository.async_transaction",
        lambda: transaction,
    )

    snapshot = asyncio.run(
        PatrolTaskExecutionRepository().async_get_patrol_execution_snapshot(9999)
    )

    assert snapshot is None


def test_async_record_patrol_execution_started_marks_task_active(monkeypatch):
    row = {
        "task_id": 2001,
        "task_type": "PATROL",
        "task_status": "WAITING_DISPATCH",
        "phase": "REQUESTED",
        "assigned_robot_id": "pinky3",
        "patrol_status": "PENDING",
    }
    transaction = FakeAsyncTransaction(row=row)
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_execution_repository.async_transaction",
        lambda: transaction,
    )

    response = asyncio.run(
        PatrolTaskExecutionRepository().async_record_patrol_execution_started(2001)
    )

    assert response == {
        "result_code": "ACCEPTED",
        "result_message": "순찰 경로 실행을 시작했습니다.",
        "reason_code": None,
        "task_id": 2001,
        "task_status": "RUNNING",
        "phase": "FOLLOW_PATROL_PATH",
        "assigned_robot_id": "pinky3",
        "cancellable": True,
    }
    assert [call[0].split()[0] for call in transaction.cursor.calls] == [
        "SELECT",
        "UPDATE",
        "UPDATE",
        "INSERT",
        "INSERT",
    ]
    assert "FOR UPDATE" in transaction.cursor.calls[0][0]
    assert "UPDATE task" in transaction.cursor.calls[1][0]
    assert "UPDATE patrol_task_detail" in transaction.cursor.calls[2][0]
    assert "INSERT INTO task_state_history" in transaction.cursor.calls[3][0]
    assert "INSERT INTO task_event_log" in transaction.cursor.calls[4][0]
    assert transaction.cursor.calls[1][1] == (
        "ACCEPTED",
        "순찰 경로 실행을 시작했습니다.",
        2001,
    )
    assert transaction.cursor.calls[2][1] == ("MOVING", 0, 2001)


def test_async_record_patrol_execution_started_rejects_terminal_task(monkeypatch):
    row = {
        "task_id": 2001,
        "task_type": "PATROL",
        "task_status": "FAILED",
        "phase": "FAILED",
        "assigned_robot_id": "pinky3",
        "patrol_status": "FAILED",
    }
    transaction = FakeAsyncTransaction(row=row)
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_execution_repository.async_transaction",
        lambda: transaction,
    )

    response = asyncio.run(
        PatrolTaskExecutionRepository().async_record_patrol_execution_started(2001)
    )

    assert response["result_code"] == "NOT_ALLOWED"
    assert response["reason_code"] == "PATROL_TASK_ALREADY_TERMINAL"
    assert [call[0].split()[0] for call in transaction.cursor.calls] == ["SELECT"]
