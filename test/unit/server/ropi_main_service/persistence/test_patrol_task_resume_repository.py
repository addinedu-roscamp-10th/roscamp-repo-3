import asyncio
import json

from server.ropi_main_service.persistence.repositories.patrol_task_resume_repository import (
    PatrolTaskResumeRepository,
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


def test_async_record_patrol_task_resume_result_updates_task_and_logs_action(
    monkeypatch,
):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 2001,
            "task_type": "PATROL",
            "task_status": "RUNNING",
            "phase": "WAIT_FALL_RESPONSE",
            "assigned_robot_id": "pinky3",
            "patrol_status": "WAITING_FALL_RESPONSE",
        }
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_resume_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    response = asyncio.run(
        PatrolTaskResumeRepository().async_record_patrol_task_resume_result(
            task_id="2001",
            caregiver_id=7,
            member_id=301,
            action_memo="119 신고 후 병원 이송",
            resume_command_response={"accepted": True},
        )
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_status"] == "RUNNING"
    assert response["phase"] == "FOLLOW_PATROL_PATH"
    assert response["assigned_robot_id"] == "pinky3"
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
        "ACCEPTED",
        "순찰을 재개합니다.",
        2001,
    )
    assert cursor.calls[2][1] == ("MOVING", 2001)
    event_payload = json.loads(cursor.calls[4][1][7])
    assert event_payload == {
        "caregiver_id": 7,
        "member_id": 301,
        "action_memo": "119 신고 후 병원 이송",
        "resume_command_response": {"accepted": True},
    }


def test_async_record_patrol_task_resume_result_rejects_wrong_phase(monkeypatch):
    cursor = RecordingAsyncCursor(
        row={
            "task_id": 2001,
            "task_type": "PATROL",
            "task_status": "RUNNING",
            "phase": "FOLLOW_PATROL_PATH",
            "assigned_robot_id": "pinky3",
            "patrol_status": "MOVING",
        }
    )
    monkeypatch.setattr(
        "server.ropi_main_service.persistence.repositories.patrol_task_resume_repository.async_transaction",
        lambda: FakeAsyncTransaction(cursor),
    )

    response = asyncio.run(
        PatrolTaskResumeRepository().async_record_patrol_task_resume_result(
            task_id="2001",
            caregiver_id=7,
            member_id=301,
            action_memo="119 신고 후 병원 이송",
            resume_command_response={"accepted": True},
        )
    )

    assert response["result_code"] == "NOT_ALLOWED"
    assert response["reason_code"] == "PATROL_NOT_WAITING_FALL_RESPONSE"
    assert [call[0].split()[0] for call in cursor.calls] == ["SELECT"]
