import asyncio

from server.ropi_main_service.persistence.repositories.fall_inference_repository import (
    FallInferenceRepository,
)


class FakeAsyncTransaction:
    def __init__(self, cursor):
        self.cursor = cursor

    async def __aenter__(self):
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        return False


class RecordingAsyncCursor:
    def __init__(self, rows=None):
        self.calls = []
        self.rows = list(rows or [])

    async def execute(self, query, params):
        self.calls.append((query, params))

    async def fetchone(self):
        if not self.rows:
            return None
        return self.rows.pop(0)


def test_repository_records_ai_inference_with_string_frame_id(monkeypatch):
    calls = []

    async def fake_async_execute(query, params):
        calls.append((query, params))
        return 1

    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.fall_inference_repository.async_execute",
        fake_async_execute,
    )

    response = asyncio.run(
        FallInferenceRepository().async_record_ai_inference(
            task_id=2001,
            robot_id="pinky3",
            stream_name="pinky3_front_patrol",
            result={
                "frame_id": "front_cam_frame_541",
                "frame_ts": "2026-04-29T12:34:56Z",
                "confidence": 0.94,
                "fall_detected": True,
            },
        )
    )

    assert response == {"result_code": "RECORDED", "rowcount": 1}
    assert "INSERT INTO ai_inference_log" in calls[0][0]
    assert calls[0][1][3] == "front_cam_frame_541"
    assert calls[0][1][5] == 0.94


def test_repository_marks_patrol_waiting_fall_response(monkeypatch):
    cursor = RecordingAsyncCursor(
        rows=[
            {
                "task_id": 2001,
                "task_status": "RUNNING",
                "phase": "FOLLOW_PATROL_PATH",
                "assigned_robot_id": "pinky3",
                "patrol_status": "MOVING",
            }
        ]
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.fall_inference_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    response = asyncio.run(
        FallInferenceRepository().async_record_fall_alert_started(
            task_id=2001,
            robot_id="pinky3",
            trigger_result={
                "result_seq": 541,
                "frame_id": "front_cam_frame_541",
                "fall_streak_ms": 1200,
            },
            command_response={"accepted": True},
        )
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["phase"] == "WAIT_FALL_RESPONSE"
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
    assert cursor.calls[1][1] == (
        "FALL_DETECTED",
        "낙상 대응 대기 상태로 전환했습니다.",
        2001,
    )
    assert cursor.calls[2][1] == ("WAITING_FALL_RESPONSE", 2001)


def test_repository_ignores_already_waiting_fall_response(monkeypatch):
    cursor = RecordingAsyncCursor(
        rows=[
            {
                "task_id": 2001,
                "task_status": "RUNNING",
                "phase": "WAIT_FALL_RESPONSE",
                "assigned_robot_id": "pinky3",
                "patrol_status": "WAITING_FALL_RESPONSE",
            }
        ]
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.fall_inference_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    response = asyncio.run(
        FallInferenceRepository().async_record_fall_alert_started(
            task_id=2001,
            robot_id="pinky3",
            trigger_result={"result_seq": 542},
            command_response={"accepted": True},
        )
    )

    assert response["result_code"] == "IGNORED"
    assert response["reason_code"] == "FALL_ALERT_ALREADY_ACTIVE"
    assert [call[0].split()[0] for call in cursor.calls] == ["SELECT"]
