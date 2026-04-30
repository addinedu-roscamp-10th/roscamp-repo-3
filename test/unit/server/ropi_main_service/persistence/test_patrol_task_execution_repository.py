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
