import asyncio

from server.ropi_main_service.application.fall_evidence_image import (
    FallEvidenceImageService,
)


class FakeFallEvidenceRepository:
    def __init__(self):
        self.calls = []

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


def test_fall_evidence_image_validates_alert_and_proxies_to_ai():
    repository = FakeFallEvidenceRepository()
    evidence_client = FakeFallEvidenceClient()
    service = FallEvidenceImageService(
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
    repository = FakeFallEvidenceRepository()
    evidence_client = FakeFallEvidenceClient()
    service = FallEvidenceImageService(
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
    repository = FakeFallEvidenceRepository()
    evidence_client = FakeFallEvidenceClient()
    service = FallEvidenceImageService(
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
    repository = FakeFallEvidenceRepository()
    evidence_client = FakeFallEvidenceClient(exc=RuntimeError("ai down"))
    service = FallEvidenceImageService(
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
    repository = FakeFallEvidenceRepository()
    evidence_client = FakeFallEvidenceClient()
    service = FallEvidenceImageService(
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
