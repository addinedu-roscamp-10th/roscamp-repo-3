import asyncio
import time

from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message
from server.ropi_main_service.ros.uds_server import RosServiceUdsServer


class FakeGoalPoseActionClient:
    def __init__(self):
        self.calls = []
        self.ready_checks = []
        self.cancel_calls = []

    def send_goal(self, *, action_name, goal, result_wait_timeout_sec=None):
        self.calls.append(
            {
                "action_name": action_name,
                "goal": goal,
                "result_wait_timeout_sec": result_wait_timeout_sec,
            }
        )
        return {
            "accepted": True,
            "status": 4,
            "result_code": "SUCCESS",
            "result_message": "navigation done",
        }

    def is_server_ready(self, *, action_name, wait_timeout_sec=0.0):
        self.ready_checks.append(
            {
                "action_name": action_name,
                "wait_timeout_sec": wait_timeout_sec,
            }
        )
        return True

    async def async_cancel_goal(self, *, task_id, action_name=None):
        self.cancel_calls.append(
            {
                "task_id": task_id,
                "action_name": action_name,
            }
        )
        return {
            "result_code": "CANCEL_REQUESTED",
            "cancel_requested": True,
            "matched_goal_count": 1,
        }

    def get_latest_feedback(self, *, task_id, action_name=None):
        return [
            {
                "task_id": task_id,
                "action_name": "/ropi/control/pinky2/navigate_to_goal",
                "action_type": "navigation",
                "feedback_type": "NAVIGATION_FEEDBACK",
                "received_at": "2026-04-28T00:00:00+00:00",
                "payload": {
                    "nav_status": "MOVING",
                    "distance_remaining_m": 1.25,
                },
            }
        ]


def test_ros_service_uds_server_dispatches_navigate_to_goal_command(tmp_path):
    socket_path = tmp_path / "ropi_ros_service.sock"
    action_client = FakeGoalPoseActionClient()

    async def scenario():
        server = RosServiceUdsServer(
            socket_path=str(socket_path),
            goal_pose_action_client=action_client,
        )
        await server.start()

        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            writer.write(
                encode_message(
                    {
                        "command": "navigate_to_goal",
                        "payload": {
                            "pinky_id": "pinky2",
                            "goal": {
                                "task_id": "task_delivery_001",
                                "nav_phase": "DELIVERY_DESTINATION",
                                "goal_pose": {
                                    "header": {"frame_id": "map", "stamp": {"sec": 0, "nanosec": 0}},
                                    "pose": {
                                        "position": {"x": 18.4, "y": 7.2, "z": 0.0},
                                        "orientation": {"x": 0.0, "y": 0.0, "z": 1.0, "w": 0.0},
                                    },
                                },
                                "timeout_sec": 120,
                            },
                        },
                    }
                )
            )
            await writer.drain()
            response = decode_message_bytes(await reader.readline())
            writer.close()
            await writer.wait_closed()
            return response
        finally:
            await server.close()

    response = asyncio.run(scenario())

    assert action_client.calls == [
        {
            "action_name": "/ropi/control/pinky2/navigate_to_goal",
            "goal": {
                "task_id": "task_delivery_001",
                "nav_phase": "DELIVERY_DESTINATION",
                "goal_pose": {
                    "header": {"frame_id": "map", "stamp": {"sec": 0, "nanosec": 0}},
                    "pose": {
                        "position": {"x": 18.4, "y": 7.2, "z": 0.0},
                        "orientation": {"x": 0.0, "y": 0.0, "z": 1.0, "w": 0.0},
                    },
                },
                "timeout_sec": 120,
            },
            "result_wait_timeout_sec": 125.0,
        }
    ]
    assert response == {
        "ok": True,
        "payload": {
            "accepted": True,
            "status": 4,
            "result_code": "SUCCESS",
            "result_message": "navigation done",
        },
    }


def test_ros_service_uds_server_dispatch_request_is_awaitable(tmp_path):
    socket_path = tmp_path / "ropi_ros_service.sock"
    action_client = FakeGoalPoseActionClient()

    async def scenario():
        server = RosServiceUdsServer(
            socket_path=str(socket_path),
            goal_pose_action_client=action_client,
        )
        try:
            return await server._dispatch_request(
                {
                    "command": "navigate_to_goal",
                    "payload": {
                        "pinky_id": "pinky2",
                        "goal": {
                            "task_id": "task_delivery_001",
                            "nav_phase": "DELIVERY_DESTINATION",
                            "timeout_sec": 120,
                        },
                    },
                }
            )
        finally:
            await server.close()

    response = asyncio.run(scenario())

    assert response["ok"] is True
    assert response["payload"]["result_code"] == "SUCCESS"


def test_ros_service_uds_server_does_not_block_event_loop_while_action_waits(tmp_path):
    socket_path = tmp_path / "ropi_ros_service.sock"

    class SlowGoalPoseActionClient(FakeGoalPoseActionClient):
        def send_goal(self, *, action_name, goal, result_wait_timeout_sec=None):
            time.sleep(0.25)
            return super().send_goal(
                action_name=action_name,
                goal=goal,
                result_wait_timeout_sec=result_wait_timeout_sec,
            )

    async def send_request(command, payload):
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        writer.write(encode_message({"command": command, "payload": payload}))
        await writer.drain()
        response = decode_message_bytes(await reader.readline())
        writer.close()
        await writer.wait_closed()
        return response

    async def scenario():
        server = RosServiceUdsServer(
            socket_path=str(socket_path),
            goal_pose_action_client=SlowGoalPoseActionClient(),
        )
        await server.start()
        try:
            started_at = time.monotonic()
            slow_task = asyncio.create_task(
                send_request(
                    "navigate_to_goal",
                    {
                        "pinky_id": "pinky2",
                        "goal": {
                            "task_id": "task_delivery_001",
                            "nav_phase": "DELIVERY_DESTINATION",
                            "timeout_sec": 120,
                        },
                    },
                )
            )
            await asyncio.sleep(0.01)
            fast_response = await send_request("unknown_command", {})
            elapsed = time.monotonic() - started_at
            await slow_task
            return elapsed, fast_response
        finally:
            await server.close()

    elapsed, fast_response = asyncio.run(scenario())

    assert elapsed < 0.2
    assert fast_response["ok"] is False
    assert fast_response["error_code"] == "UNKNOWN_COMMAND"


def test_ros_service_uds_server_reports_runtime_readiness(tmp_path):
    socket_path = tmp_path / "ropi_ros_service.sock"
    action_client = FakeGoalPoseActionClient()

    async def scenario():
        server = RosServiceUdsServer(
            socket_path=str(socket_path),
            goal_pose_action_client=action_client,
        )
        await server.start()

        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            writer.write(
                encode_message(
                    {
                        "command": "get_runtime_status",
                        "payload": {
                            "pinky_id": "pinky2",
                            "arm_ids": ["arm1", "arm2"],
                        },
                    }
                )
            )
            await writer.drain()
            response = decode_message_bytes(await reader.readline())
            writer.close()
            await writer.wait_closed()
            return response
        finally:
            await server.close()

    response = asyncio.run(scenario())

    assert action_client.ready_checks == [
        {
            "action_name": "/ropi/control/pinky2/navigate_to_goal",
            "wait_timeout_sec": 0.0,
        }
    ]
    assert response == {
        "ok": True,
        "payload": {
            "ready": False,
            "checks": [
                {
                    "name": "pinky2.navigate_to_goal",
                    "ready": True,
                    "action_name": "/ropi/control/pinky2/navigate_to_goal",
                },
                {
                    "name": "arm1.execute_manipulation",
                    "ready": False,
                    "action_name": "/ropi/arm/arm1/execute_manipulation",
                    "error": "manipulation action client is not configured",
                },
                {
                    "name": "arm2.execute_manipulation",
                    "ready": False,
                    "action_name": "/ropi/arm/arm2/execute_manipulation",
                    "error": "manipulation action client is not configured",
                },
            ],
        },
    }


def test_ros_service_uds_server_dispatches_cancel_action_command(tmp_path):
    socket_path = tmp_path / "ropi_ros_service.sock"
    action_client = FakeGoalPoseActionClient()

    async def scenario():
        server = RosServiceUdsServer(
            socket_path=str(socket_path),
            goal_pose_action_client=action_client,
        )
        await server.start()

        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            writer.write(
                encode_message(
                    {
                        "command": "cancel_action",
                        "payload": {
                            "task_id": "task_delivery_001",
                        },
                    }
                )
            )
            await writer.drain()
            response = decode_message_bytes(await reader.readline())
            writer.close()
            await writer.wait_closed()
            return response
        finally:
            await server.close()

    response = asyncio.run(scenario())

    assert action_client.cancel_calls == [
        {
            "task_id": "task_delivery_001",
            "action_name": None,
        }
    ]
    assert response == {
        "ok": True,
        "payload": {
            "result_code": "CANCEL_REQUESTED",
            "result_message": "action cancel request was accepted.",
            "task_id": "task_delivery_001",
            "action_name": None,
            "cancel_requested": True,
            "details": [
                {
                    "client": "navigation",
                    "result_code": "CANCEL_REQUESTED",
                    "cancel_requested": True,
                    "matched_goal_count": 1,
                }
            ],
        },
    }


def test_ros_service_uds_server_dispatches_get_action_feedback_command(tmp_path):
    socket_path = tmp_path / "ropi_ros_service.sock"
    action_client = FakeGoalPoseActionClient()

    async def scenario():
        server = RosServiceUdsServer(
            socket_path=str(socket_path),
            goal_pose_action_client=action_client,
        )
        await server.start()

        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            writer.write(
                encode_message(
                    {
                        "command": "get_action_feedback",
                        "payload": {
                            "task_id": "task_delivery_001",
                        },
                    }
                )
            )
            await writer.drain()
            response = decode_message_bytes(await reader.readline())
            writer.close()
            await writer.wait_closed()
            return response
        finally:
            await server.close()

    response = asyncio.run(scenario())

    assert response == {
        "ok": True,
        "payload": {
            "result_code": "FOUND",
            "task_id": "task_delivery_001",
            "action_name": None,
            "feedback": [
                {
                    "client": "navigation",
                    "task_id": "task_delivery_001",
                    "action_name": "/ropi/control/pinky2/navigate_to_goal",
                    "action_type": "navigation",
                    "feedback_type": "NAVIGATION_FEEDBACK",
                    "received_at": "2026-04-28T00:00:00+00:00",
                    "payload": {
                        "nav_status": "MOVING",
                        "distance_remaining_m": 1.25,
                    },
                }
            ],
        },
    }
