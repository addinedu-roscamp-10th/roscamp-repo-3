import asyncio

from server.ropi_main_service.persistence.repositories.guide_task_lifecycle_repository import (
    GuideTaskLifecycleRepository,
)


class FakeSyncCursor:
    def __init__(self, row=None):
        self.calls = []
        self._row = row or {
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "WAITING_DISPATCH",
            "phase": "WAIT_GUIDE_START_CONFIRM",
            "assigned_robot_id": "pinky1",
            "guide_phase": "WAIT_GUIDE_START_CONFIRM",
            "target_track_id": None,
        }
        self._last_query = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))
        self._last_query = query

    def fetchone(self):
        if "FOR UPDATE" in self._last_query:
            return self._row
        return None


class FakeConnection:
    def __init__(self, row=None):
        self.cursor_instance = FakeSyncCursor(row=row)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def begin(self):
        pass

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeAsyncCursor:
    def __init__(self, row=None):
        self.calls = []
        self._row = row or {
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": "pinky1",
            "guide_phase": "WAIT_TARGET_TRACKING",
            "target_track_id": None,
        }
        self._last_query = ""

    async def execute(self, query, params=None):
        self.calls.append((query, params))
        self._last_query = query

    async def fetchone(self):
        if "FOR UPDATE" in self._last_query:
            return self._row
        return None


class FakeAsyncTransaction:
    def __init__(self, row=None):
        self.cursor = FakeAsyncCursor(row=row)

    async def __aenter__(self):
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_record_wait_target_tracking_acceptance_updates_task_detail_history_and_event():
    connection = FakeConnection()
    repository = GuideTaskLifecycleRepository(connection_factory=lambda: connection)

    response = repository.record_command_result(
        task_id=3001,
        pinky_id="pinky1",
        command_type="WAIT_TARGET_TRACKING",
        command_response={"accepted": True, "message": ""},
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "WAIT_TARGET_TRACKING"
    assert response["guide_phase"] == "WAIT_TARGET_TRACKING"
    assert connection.committed is True
    assert connection.rolled_back is False
    assert "UPDATE task" in connection.cursor_instance.calls[1][0]
    assert connection.cursor_instance.calls[1][1][:4] == (
        "RUNNING",
        "WAIT_TARGET_TRACKING",
        "GUIDE_COMMAND_ACCEPTED",
        "ACCEPTED",
    )
    assert "UPDATE guide_task_detail" in connection.cursor_instance.calls[2][0]
    assert "INSERT INTO task_state_history" in connection.cursor_instance.calls[3][0]
    assert "INSERT INTO task_event_log" in connection.cursor_instance.calls[4][0]


def test_record_command_rejection_keeps_current_phase_and_writes_event_only():
    connection = FakeConnection()
    repository = GuideTaskLifecycleRepository(connection_factory=lambda: connection)

    response = repository.record_command_result(
        task_id=3001,
        pinky_id="pinky1",
        command_type="WAIT_TARGET_TRACKING",
        command_response={
            "accepted": False,
            "reason_code": "GUIDE_STATE_MISMATCH",
            "message": "invalid order",
        },
    )

    assert response["result_code"] == "REJECTED"
    assert response["task_status"] == "WAITING_DISPATCH"
    assert response["phase"] == "WAIT_GUIDE_START_CONFIRM"
    assert "UPDATE task" in connection.cursor_instance.calls[1][0]
    assert "INSERT INTO task_event_log" in connection.cursor_instance.calls[2][0]
    assert len(connection.cursor_instance.calls) == 3


def test_async_record_finish_user_cancel_finalizes_cancelled_task():
    transaction = FakeAsyncTransaction()
    repository = GuideTaskLifecycleRepository(
        async_transaction_factory=lambda: transaction,
    )

    response = asyncio.run(
        repository.async_record_command_result(
            task_id=3001,
            pinky_id="pinky1",
            command_type="FINISH_GUIDANCE",
            finish_reason="USER_CANCELLED",
            command_response={"accepted": True, "message": "finished"},
        )
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_status"] == "CANCELLED"
    assert response["phase"] == "GUIDANCE_CANCELLED"
    assert response["guide_phase"] == "CANCELLED"
    assert "UPDATE task" in transaction.cursor.calls[1][0]
    assert transaction.cursor.calls[1][1][:4] == (
        "CANCELLED",
        "GUIDANCE_CANCELLED",
        "USER_CANCELLED",
        "ACCEPTED",
    )
    assert "UPDATE guide_task_detail" in transaction.cursor.calls[2][0]
    assert "INSERT INTO task_state_history" in transaction.cursor.calls[3][0]
    assert "INSERT INTO task_event_log" in transaction.cursor.calls[4][0]


def test_record_lifecycle_rejects_non_numeric_task_id():
    repository = GuideTaskLifecycleRepository()

    response = repository.record_command_result(
        task_id="guide_legacy_1",
        pinky_id="pinky1",
        command_type="WAIT_TARGET_TRACKING",
        command_response={"accepted": True},
    )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "TASK_ID_INVALID"
