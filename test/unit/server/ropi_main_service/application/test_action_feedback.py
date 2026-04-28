import asyncio

from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.application.action_feedback import RosActionFeedbackService
from server.ropi_main_service.application.action_feedback_sampling import (
    ActionFeedbackSampleBuilder,
    FeedbackSamplingGate,
)


class FakeActionFeedbackCommandClient:
    def __init__(self):
        self.calls = []
        self.response = {
            "result_code": "FOUND",
            "task_id": "101",
            "feedback": [],
        }

    def send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
                "mode": "sync",
            }
        )
        return dict(self.response)

    async def async_send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
                "mode": "async",
            }
        )
        return dict(self.response)


class FakeRobotDataLogRepository:
    def __init__(self):
        self.samples = []

    def insert_feedback_sample(self, **kwargs):
        self.samples.append({"mode": "sync", **kwargs})

    async def async_insert_feedback_sample(self, **kwargs):
        self.samples.append({"mode": "async", **kwargs})


class FakeRobotDataLogWriter:
    def __init__(self):
        self.samples = []

    def enqueue_robot_data_log_sample(self, sample):
        self.samples.append(sample)
        return True


def test_action_feedback_sample_builder_skips_unknown_robot_action_name():
    builder = ActionFeedbackSampleBuilder(runtime_config=DeliveryRuntimeConfig())

    sample = builder.build_sample(
        {
            "task_id": "101",
            "action_name": "/unknown/action",
            "feedback_type": "ACTION_FEEDBACK",
            "payload": {},
        }
    )

    assert sample is None


def test_feedback_sampling_gate_throttles_same_feedback_key():
    gate = FeedbackSamplingGate(sample_interval_sec=5.0)
    feedback = {
        "task_id": "101",
        "action_name": "/ropi/control/pinky2/navigate_to_goal",
        "feedback_type": "NAVIGATION_FEEDBACK",
    }

    assert gate.should_sample(feedback) is True
    assert gate.should_sample(feedback) is False


def test_get_latest_feedback_sends_get_action_feedback_command():
    command_client = FakeActionFeedbackCommandClient()
    service = RosActionFeedbackService(command_client=command_client)

    response = service.get_latest_feedback(task_id=101)

    assert response["result_code"] == "FOUND"
    assert command_client.calls == [
        {
            "command": "get_action_feedback",
            "payload": {"task_id": "101"},
            "timeout": 1.0,
            "mode": "sync",
        }
    ]


def test_get_latest_feedback_samples_navigation_feedback_to_robot_data_log():
    command_client = FakeActionFeedbackCommandClient()
    command_client.response = {
        "result_code": "FOUND",
        "task_id": "101",
        "feedback": [
            {
                "client": "navigation",
                "task_id": "101",
                "action_name": "/ropi/control/pinky2/navigate_to_goal",
                "feedback_type": "NAVIGATION_FEEDBACK",
                "payload": {
                    "nav_status": "MOVING",
                    "distance_remaining_m": 1.25,
                    "current_pose": {
                        "header": {"frame_id": "map"},
                        "pose": {
                            "position": {"x": 1.2, "y": 0.8, "z": 0.0},
                            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                        },
                    },
                },
            }
        ],
    }
    robot_data_log_repository = FakeRobotDataLogRepository()
    service = RosActionFeedbackService(
        command_client=command_client,
        robot_data_log_repository=robot_data_log_repository,
        runtime_config=DeliveryRuntimeConfig(pinky_id="pinky2"),
        sample_interval_sec=5.0,
    )

    service.get_latest_feedback(task_id=101)
    service.get_latest_feedback(task_id=101)

    assert robot_data_log_repository.samples == [
        {
            "mode": "sync",
            "robot_id": "pinky2",
            "task_id": 101,
            "data_type": "NAVIGATION_FEEDBACK",
            "pose_x": 1.2,
            "pose_y": 0.8,
            "pose_yaw": 0.0,
            "battery_percent": None,
            "payload": command_client.response["feedback"][0],
        }
    ]


def test_async_get_latest_feedback_prefers_async_command_client():
    command_client = FakeActionFeedbackCommandClient()
    service = RosActionFeedbackService(command_client=command_client)

    response = asyncio.run(service.async_get_latest_feedback(task_id=101))

    assert response["result_code"] == "FOUND"
    assert command_client.calls == [
        {
            "command": "get_action_feedback",
            "payload": {"task_id": "101"},
            "timeout": 1.0,
            "mode": "async",
        }
    ]


def test_async_get_latest_feedback_samples_manipulation_feedback_with_arm_robot_mapping():
    command_client = FakeActionFeedbackCommandClient()
    command_client.response = {
        "result_code": "FOUND",
        "task_id": "101",
        "feedback": [
            {
                "client": "manipulation",
                "task_id": "101",
                "action_name": "/ropi/arm/arm1/execute_manipulation",
                "feedback_type": "MANIPULATION_FEEDBACK",
                "payload": {
                    "processed_quantity": 1,
                },
            }
        ],
    }
    robot_data_log_repository = FakeRobotDataLogRepository()
    robot_data_log_writer = FakeRobotDataLogWriter()
    service = RosActionFeedbackService(
        command_client=command_client,
        robot_data_log_repository=robot_data_log_repository,
        robot_data_log_writer=robot_data_log_writer,
        runtime_config=DeliveryRuntimeConfig(
            pickup_arm_id="arm1",
            pickup_arm_robot_id="jetcobot1",
        ),
        sample_interval_sec=0.0,
    )

    asyncio.run(service.async_get_latest_feedback(task_id=101))

    assert robot_data_log_repository.samples == []
    assert robot_data_log_writer.samples == [
        {
            "robot_id": "jetcobot1",
            "task_id": 101,
            "data_type": "MANIPULATION_FEEDBACK",
            "pose_x": None,
            "pose_y": None,
            "pose_yaw": None,
            "battery_percent": None,
            "payload": command_client.response["feedback"][0],
        }
    ]
