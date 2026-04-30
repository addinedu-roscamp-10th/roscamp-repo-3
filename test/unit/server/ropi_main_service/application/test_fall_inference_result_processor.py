import asyncio

from server.ropi_main_service.application.fall_inference_result import (
    FallInferenceResultProcessor,
)


class FakeRepository:
    def __init__(self, active_task=None):
        self.active_task = active_task
        self.inference_logs = []
        self.alert_records = []

    async def async_get_active_patrol_task_for_robot(self, robot_id):
        return self.active_task

    async def async_record_ai_inference(self, **kwargs):
        self.inference_logs.append(kwargs)
        return {"result_code": "RECORDED"}

    async def async_record_fall_alert_started(self, **kwargs):
        self.alert_records.append(kwargs)
        return {
            "result_code": "ACCEPTED",
            "task_id": kwargs["task_id"],
            "task_status": "RUNNING",
            "phase": "WAIT_FALL_RESPONSE",
            "assigned_robot_id": kwargs["robot_id"],
            "cancellable": True,
        }


class FakeCommandClient:
    def __init__(self, response=None):
        self.response = response or {"accepted": True, "message": ""}
        self.calls = []

    async def async_send_command(self, command, payload, timeout=None):
        self.calls.append((command, payload, timeout))
        return self.response


class FakeCommandExecutionRecorder:
    def __init__(self):
        self.specs = []

    async def async_record(self, spec, command_runner):
        self.specs.append(spec)
        return await command_runner()


class FakeTaskEventPublisher:
    def __init__(self):
        self.events = []

    async def publish(self, event_type, payload):
        self.events.append((event_type, payload))


def test_processor_records_inference_and_starts_fall_response_after_threshold():
    repository = FakeRepository(
        active_task={
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "FOLLOW_PATROL_PATH",
            "assigned_robot_id": "pinky3",
            "patrol_status": "MOVING",
        }
    )
    command_client = FakeCommandClient()
    recorder = FakeCommandExecutionRecorder()
    publisher = FakeTaskEventPublisher()
    processor = FallInferenceResultProcessor(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=recorder,
        task_event_publisher=publisher,
        pinky_id="pinky3",
    )

    summary = asyncio.run(
        processor.async_process_batch(
            {
                "batch_end_seq": 541,
                "results": [
                    {
                        "result_seq": 541,
                        "frame_id": "front_cam_frame_541",
                        "frame_ts": "2026-04-29T12:34:56Z",
                        "fall_detected": True,
                        "confidence": 0.94,
                        "fall_streak_ms": 1200,
                    }
                ],
            }
        )
    )

    assert summary == {
        "processed_count": 1,
        "logged_count": 1,
        "alert_started_count": 1,
        "ignored_count": 0,
    }
    assert repository.inference_logs[0]["task_id"] == 2001
    assert repository.inference_logs[0]["robot_id"] == "pinky3"
    assert repository.inference_logs[0]["result"]["frame_id"] == "front_cam_frame_541"
    assert command_client.calls == [
        (
            "fall_response_control",
            {
                "pinky_id": "pinky3",
                "task_id": "2001",
                "command_type": "START_FALL_ALERT",
            },
            5.0,
        )
    ]
    assert recorder.specs[0].command_phase == "FALL_ALERT_START"
    assert repository.alert_records[0]["task_id"] == 2001
    assert repository.alert_records[0]["command_response"] == {"accepted": True, "message": ""}
    assert publisher.events == [
        (
            "TASK_UPDATED",
            {
                "source": "FALL_ALERT",
                "task_id": 2001,
                "task_type": "PATROL",
                "task_status": "RUNNING",
                "phase": "WAIT_FALL_RESPONSE",
                "assigned_robot_id": "pinky3",
                "latest_reason_code": "FALL_DETECTED",
                "result_code": "ACCEPTED",
                "result_message": "낙상 대응 대기 상태로 전환했습니다.",
                "cancel_requested": None,
                "cancellable": True,
            },
        )
    ]


def test_processor_logs_below_threshold_without_command():
    repository = FakeRepository(
        active_task={
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "FOLLOW_PATROL_PATH",
            "assigned_robot_id": "pinky3",
        }
    )
    command_client = FakeCommandClient()
    processor = FallInferenceResultProcessor(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=FakeCommandExecutionRecorder(),
        pinky_id="pinky3",
    )

    summary = asyncio.run(
        processor.async_process_batch(
            {
                "batch_end_seq": 541,
                "results": [
                    {
                        "result_seq": 541,
                        "frame_id": "front_cam_frame_541",
                        "frame_ts": "2026-04-29T12:34:56Z",
                        "fall_detected": True,
                        "fall_streak_ms": 800,
                    }
                ],
            }
        )
    )

    assert summary["logged_count"] == 1
    assert summary["alert_started_count"] == 0
    assert summary["ignored_count"] == 1
    assert command_client.calls == []
    assert repository.alert_records == []


def test_processor_does_not_duplicate_alert_for_waiting_task():
    repository = FakeRepository(
        active_task={
            "task_id": 2001,
            "task_status": "RUNNING",
            "phase": "WAIT_FALL_RESPONSE",
            "assigned_robot_id": "pinky3",
        }
    )
    command_client = FakeCommandClient()
    processor = FallInferenceResultProcessor(
        repository=repository,
        command_client=command_client,
        command_execution_recorder=FakeCommandExecutionRecorder(),
        pinky_id="pinky3",
    )

    summary = asyncio.run(
        processor.async_process_batch(
            {
                "batch_end_seq": 542,
                "results": [
                    {
                        "result_seq": 542,
                        "frame_id": "front_cam_frame_542",
                        "frame_ts": "2026-04-29T12:34:57Z",
                        "fall_detected": True,
                        "fall_streak_ms": 1500,
                    }
                ],
            }
        )
    )

    assert summary["logged_count"] == 1
    assert summary["alert_started_count"] == 0
    assert summary["ignored_count"] == 1
    assert command_client.calls == []
