from server.ropi_main_service.persistence.repositories.guide_phase_snapshot_repository import (
    GuidePhaseSnapshotRepository,
)


class FakeSyncCursor:
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


def test_record_ready_to_start_updates_phase_and_numeric_track_id():
    connection = FakeConnection()
    repository = GuidePhaseSnapshotRepository(connection_factory=lambda: connection)

    response = repository.record_phase_snapshot(
        task_id=3001,
        pinky_id="pinky1",
        guide_phase="READY_TO_START_GUIDANCE",
        target_track_id=17,
        reason_code="",
        seq=42,
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "READY_TO_START_GUIDANCE"
    assert response["guide_phase"] == "READY_TO_START_GUIDANCE"
    assert response["target_track_id"] == 17
    assert connection.committed is True
    assert "UPDATE task" in connection.cursor_instance.calls[1][0]
    assert connection.cursor_instance.calls[1][1][:4] == (
        "RUNNING",
        "READY_TO_START_GUIDANCE",
        "GUIDE_PHASE_SNAPSHOT",
        "ACCEPTED",
    )
    assert "UPDATE guide_task_detail" in connection.cursor_instance.calls[2][0]
    assert connection.cursor_instance.calls[2][1] == (
        "READY_TO_START_GUIDANCE",
        17,
        3001,
    )
    assert "INSERT INTO task_state_history" in connection.cursor_instance.calls[3][0]
    assert "INSERT INTO task_event_log" in connection.cursor_instance.calls[4][0]


def test_record_wait_reidentify_keeps_task_running_without_control_command():
    connection = FakeConnection(
        row={
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "GUIDANCE_RUNNING",
            "assigned_robot_id": "pinky1",
            "guide_phase": "GUIDANCE_RUNNING",
            "target_track_id": 17,
        }
    )
    repository = GuidePhaseSnapshotRepository(connection_factory=lambda: connection)

    response = repository.record_phase_snapshot(
        task_id=3001,
        pinky_id="pinky1",
        guide_phase="WAIT_REIDENTIFY",
        target_track_id=17,
        reason_code="TARGET_LOST",
        seq=77,
    )

    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "WAIT_REIDENTIFY"
    assert response["guide_phase"] == "WAIT_REIDENTIFY"
    assert response["target_track_id"] == 17


def test_record_guidance_finished_finalizes_completed_task_immediately():
    connection = FakeConnection(
        row={
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "GUIDANCE_RUNNING",
            "assigned_robot_id": "pinky1",
            "guide_phase": "GUIDANCE_RUNNING",
            "target_track_id": 17,
        }
    )
    repository = GuidePhaseSnapshotRepository(connection_factory=lambda: connection)

    response = repository.record_phase_snapshot(
        task_id=3001,
        pinky_id="pinky1",
        guide_phase="GUIDANCE_FINISHED",
        target_track_id=-1,
        reason_code="ARRIVED",
        seq=101,
    )

    assert response["task_status"] == "COMPLETED"
    assert response["phase"] == "GUIDANCE_FINISHED"
    assert response["guide_phase"] == "GUIDANCE_FINISHED"
    assert response["target_track_id"] == 17
    assert connection.cursor_instance.calls[1][1][:4] == (
        "COMPLETED",
        "GUIDANCE_FINISHED",
        "ARRIVED",
        "ACCEPTED",
    )
    assert connection.cursor_instance.calls[1][1][6] is True


def test_record_snapshot_rejects_terminal_task_without_reopening():
    connection = FakeConnection(
        row={
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "COMPLETED",
            "phase": "GUIDANCE_FINISHED",
            "assigned_robot_id": "pinky1",
            "guide_phase": "GUIDANCE_FINISHED",
            "target_track_id": 17,
        }
    )
    repository = GuidePhaseSnapshotRepository(connection_factory=lambda: connection)

    response = repository.record_phase_snapshot(
        task_id=3001,
        pinky_id="pinky1",
        guide_phase="WAIT_REIDENTIFY",
        target_track_id=17,
        reason_code="TARGET_LOST",
        seq=102,
    )

    assert response["result_code"] == "IGNORED"
    assert response["reason_code"] == "TASK_ALREADY_FINISHED"
    assert len(connection.cursor_instance.calls) == 1
