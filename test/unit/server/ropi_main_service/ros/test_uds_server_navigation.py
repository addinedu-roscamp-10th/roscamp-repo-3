import asyncio

from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message
from server.ropi_main_service.ros.uds_server import RosServiceUdsServer


class FakeGoalPoseActionClient:
    def __init__(self):
        self.calls = []
        self.ready_checks = []

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
