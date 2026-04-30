import asyncio
from datetime import datetime

from server.ropi_main_service.application.task_monitor import TaskMonitorService


class FakeTaskMonitorRepository:
    def __init__(self):
        self.calls = []
        self.snapshot = {
            "last_event_seq": 91,
            "tasks": [
                {
                    "task_id": 2001,
                    "task_type": "PATROL",
                    "task_status": "RUNNING",
                    "task_outcome": None,
                    "phase": "WAIT_FALL_RESPONSE",
                    "assigned_robot_id": "pinky3",
                    "patrol_area_id": "ward_3f",
                    "patrol_area_name": "3층 병동",
                    "patrol_area_revision": 2,
                    "latest_reason_code": "FALL_DETECTED",
                    "requested_at": datetime(2026, 4, 30, 10, 0, 0),
                    "started_at": datetime(2026, 4, 30, 10, 1, 0),
                    "finished_at": None,
                    "updated_at": datetime(2026, 4, 30, 10, 2, 0),
                    "latest_feedback_payload_json": {
                        "feedback_summary": "MOVING / 남은 거리 1.25m",
                        "pose": {"x": 1.2, "y": 0.4, "yaw": 0.0},
                    },
                    "latest_feedback_updated_at": datetime(2026, 4, 30, 10, 1, 30),
                    "latest_robot_id": "pinky3",
                    "runtime_state": "RUNNING",
                    "battery_percent": 88.5,
                    "pose_x": 1.2,
                    "pose_y": 0.4,
                    "pose_yaw": 0.0,
                    "frame_id": "map",
                    "last_seen_at": datetime(2026, 4, 30, 10, 1, 35),
                    "latest_alert_payload_json": {
                        "trigger_result": {
                            "result_seq": 44,
                            "frame_id": "frame-44",
                            "fall_streak_ms": 1200,
                            "evidence_image_id": "fall-2001-44",
                            "evidence_image_available": True,
                            "zone_name": "3층 복도",
                            "alert_pose": {"x": 0.9308, "y": 0.185, "yaw": 0.0},
                        }
                    },
                    "latest_alert_id": 17,
                    "latest_alert_occurred_at": datetime(2026, 4, 30, 10, 2, 0),
                }
            ],
        }

    def get_task_monitor_snapshot(self, **kwargs):
        self.calls.append(kwargs)
        return self.snapshot

    async def async_get_task_monitor_snapshot(self, **kwargs):
        self.calls.append(kwargs)
        return self.snapshot

    def get_fall_evidence_alert_candidates(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {
                "task_id": 2001,
                "task_type": "PATROL",
                "assigned_robot_id": "pinky3",
                "alert_id": 17,
                "robot_id": "pinky3",
                "payload_json": {
                    "trigger_result": {
                        "result_seq": 541,
                        "frame_id": "front_cam_frame_541",
                        "evidence_image_id": "fall_evidence_pinky3_541",
                        "evidence_image_available": True,
                    }
                },
            }
        ]

    async def async_get_fall_evidence_alert_candidates(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {
                "task_id": 2001,
                "task_type": "PATROL",
                "assigned_robot_id": "pinky3",
                "alert_id": 17,
                "robot_id": "pinky3",
                "payload_json": {
                    "trigger_result": {
                        "result_seq": 541,
                        "frame_id": "front_cam_frame_541",
                        "evidence_image_id": "fall_evidence_pinky3_541",
                        "evidence_image_available": True,
                    }
                },
            }
        ]


class FakeFallEvidenceClient:
    def __init__(self, response=None, exc=None):
        self.calls = []
        self.response = response or {
            "result_code": "OK",
            "result_message": None,
            "evidence_image_id": "fall_evidence_pinky3_541",
            "result_seq": 541,
            "frame_id": "front_cam_frame_541",
            "frame_ts": "2026-04-30T06:09:38Z",
            "image_format": "jpeg",
            "image_encoding": "base64",
            "image_data": "/9j/AA==",
            "image_width_px": 640,
            "image_height_px": 480,
            "detections": [
                {
                    "class_name": "fall",
                    "confidence": 0.87,
                    "bbox_xyxy": [120, 88, 430, 360],
                }
            ],
        }
        self.exc = exc

    def query_evidence_image(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.response

    async def async_query_evidence_image(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.response


def test_task_monitor_snapshot_formats_nested_feedback_robot_and_alert():
    repository = FakeTaskMonitorRepository()
    service = TaskMonitorService(repository=repository)

    response = service.get_task_monitor_snapshot(
        consumer_id="ui-admin-task-monitor",
        task_types=["patrol"],
        statuses=["running"],
        include_recent_terminal=False,
        recent_terminal_limit=1000,
        limit=500,
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["last_event_seq"] == 91
    assert response["consumer_id"] == "ui-admin-task-monitor"
    assert repository.calls == [
        {
            "task_types": ("PATROL",),
            "statuses": ("RUNNING",),
            "limit": 200,
        }
    ]

    task = response["tasks"][0]
    assert task["task_id"] == 2001
    assert task["task_type"] == "PATROL"
    assert task["task_status"] == "RUNNING"
    assert task["phase"] == "WAIT_FALL_RESPONSE"
    assert task["assigned_robot_id"] == "pinky3"
    assert task["cancellable"] is True
    assert task["patrol_area_name"] == "3층 병동"
    assert task["latest_feedback"] == {
        "feedback_summary": "MOVING / 남은 거리 1.25m",
        "pose": {"x": 1.2, "y": 0.4, "yaw": 0.0},
        "updated_at": "2026-04-30T10:01:30",
    }
    assert task["latest_robot"] == {
        "robot_id": "pinky3",
        "runtime_state": "RUNNING",
        "battery_percent": 88.5,
        "pose": {"x": 1.2, "y": 0.4, "yaw": 0.0, "frame_id": "map"},
        "last_seen_at": "2026-04-30T10:01:35",
    }
    assert task["latest_alert"]["alert_id"] == 17
    assert task["latest_alert"]["result_seq"] == 44
    assert task["latest_alert"]["evidence_image_id"] == "fall-2001-44"
    assert task["latest_alert"]["alert_pose"] == {"x": 0.9308, "y": 0.185, "yaw": 0.0}


def test_task_monitor_snapshot_defaults_to_active_plus_recent_terminal_statuses():
    repository = FakeTaskMonitorRepository()
    repository.snapshot = {
        "last_event_seq": 5,
        "tasks": [
            {"task_id": 1, "task_status": "RUNNING"},
            {"task_id": 2, "task_status": "COMPLETED"},
            {"task_id": 3, "task_status": "FAILED"},
        ],
    }
    service = TaskMonitorService(repository=repository)

    response = service.get_task_monitor_snapshot(recent_terminal_limit=1)

    assert repository.calls[0]["statuses"] == (
        "WAITING",
        "WAITING_DISPATCH",
        "READY",
        "ASSIGNED",
        "RUNNING",
        "CANCEL_REQUESTED",
        "CANCELLING",
        "PREEMPTING",
        "COMPLETED",
        "CANCELLED",
        "FAILED",
    )
    assert [task["task_id"] for task in response["tasks"]] == [1, 2]


def test_task_monitor_snapshot_async_uses_async_repository_method():
    repository = FakeTaskMonitorRepository()
    service = TaskMonitorService(repository=repository)

    response = asyncio.run(service.async_get_task_monitor_snapshot(task_types=["patrol"]))

    assert response["result_code"] == "ACCEPTED"
    assert repository.calls[0]["task_types"] == ("PATROL",)


def test_fall_evidence_image_validates_alert_and_proxies_to_ai():
    repository = FakeTaskMonitorRepository()
    evidence_client = FakeFallEvidenceClient()
    service = TaskMonitorService(
        repository=repository,
        evidence_client=evidence_client,
    )

    response = service.get_fall_evidence_image(
        consumer_id="ui-admin-task-monitor",
        task_id=2001,
        alert_id="17",
        evidence_image_id="fall_evidence_pinky3_541",
        result_seq=541,
    )

    assert response["result_code"] == "OK"
    assert response["task_id"] == 2001
    assert response["alert_id"] == "17"
    assert response["evidence_image_id"] == "fall_evidence_pinky3_541"
    assert response["image_width_px"] == 640
    assert repository.calls[-1] == {
        "task_id": 2001,
        "limit": 20,
    }
    assert evidence_client.calls == [
        {
            "consumer_id": "control_service_ai_fall",
            "evidence_image_id": "fall_evidence_pinky3_541",
            "result_seq": 541,
            "pinky_id": "pinky3",
        }
    ]


def test_fall_evidence_image_rejects_mismatched_evidence_without_ai_call():
    repository = FakeTaskMonitorRepository()
    evidence_client = FakeFallEvidenceClient()
    service = TaskMonitorService(
        repository=repository,
        evidence_client=evidence_client,
    )

    response = service.get_fall_evidence_image(
        consumer_id="ui-admin-task-monitor",
        task_id=2001,
        alert_id="17",
        evidence_image_id="other-image",
        result_seq=541,
    )

    assert response["result_code"] == "FORBIDDEN"
    assert response["reason_code"] == "EVIDENCE_OWNERSHIP_MISMATCH"
    assert evidence_client.calls == []


def test_fall_evidence_image_rejects_invalid_result_seq_before_ai_call():
    repository = FakeTaskMonitorRepository()
    evidence_client = FakeFallEvidenceClient()
    service = TaskMonitorService(
        repository=repository,
        evidence_client=evidence_client,
    )

    response = service.get_fall_evidence_image(
        consumer_id="ui-admin-task-monitor",
        task_id=2001,
        alert_id="17",
        evidence_image_id="fall_evidence_pinky3_541",
        result_seq="abc",
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "RESULT_SEQ_INVALID"
    assert evidence_client.calls == []


def test_fall_evidence_image_maps_upstream_failure():
    repository = FakeTaskMonitorRepository()
    evidence_client = FakeFallEvidenceClient(exc=RuntimeError("ai down"))
    service = TaskMonitorService(
        repository=repository,
        evidence_client=evidence_client,
    )

    response = service.get_fall_evidence_image(
        consumer_id="ui-admin-task-monitor",
        task_id=2001,
        alert_id="17",
        evidence_image_id="fall_evidence_pinky3_541",
        result_seq=541,
    )

    assert response["result_code"] == "UPSTREAM_UNAVAILABLE"
    assert response["reason_code"] == "AI_EVIDENCE_QUERY_FAILED"
    assert "ai down" in response["result_message"]


def test_fall_evidence_image_async_uses_async_repository_and_client():
    repository = FakeTaskMonitorRepository()
    evidence_client = FakeFallEvidenceClient()
    service = TaskMonitorService(
        repository=repository,
        evidence_client=evidence_client,
    )

    response = asyncio.run(
        service.async_get_fall_evidence_image(
            consumer_id="ui-admin-task-monitor",
            task_id=2001,
            alert_id="17",
            evidence_image_id="fall_evidence_pinky3_541",
            result_seq=541,
        )
    )

    assert response["result_code"] == "OK"
    assert evidence_client.calls[0]["evidence_image_id"] == "fall_evidence_pinky3_541"
