import asyncio

from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message
from server.ropi_main_service.ros.uds_server import RosServiceUdsServer


class FakeGoalPoseActionClient:
    def __init__(self):
        self.calls = []

    def send_goal(self, *, action_name, goal):
        self.calls.append(
            {
                "action_name": action_name,
                "goal": goal,
            }
        )
        return {
            "accepted": True,
            "goal_handle_id": "goal_handle_001",
        }


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
        }
    ]
    assert response == {
        "ok": True,
        "payload": {
            "accepted": True,
            "goal_handle_id": "goal_handle_001",
        },
    }
