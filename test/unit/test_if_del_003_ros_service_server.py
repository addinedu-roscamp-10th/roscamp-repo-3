import asyncio

from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message
from server.ropi_main_service.ros.uds_server import RosServiceUdsServer


class FakeGoalPoseActionClient:
    def send_goal(self, *, action_name, goal):
        return {
            "accepted": True,
            "goal_handle_id": "goal_handle_nav",
        }


class FakeManipulationActionClient:
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
            "goal_handle_id": "goal_handle_manipulation",
        }


def test_ros_service_uds_server_dispatches_execute_manipulation_command(tmp_path):
    socket_path = tmp_path / "ropi_ros_service.sock"
    manipulation_client = FakeManipulationActionClient()

    async def scenario():
        server = RosServiceUdsServer(
            socket_path=str(socket_path),
            goal_pose_action_client=FakeGoalPoseActionClient(),
            manipulation_action_client=manipulation_client,
        )
        await server.start()

        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            writer.write(
                encode_message(
                    {
                        "command": "execute_manipulation",
                        "payload": {
                            "arm_id": "arm1",
                            "goal": {
                                "task_id": "task_delivery_001",
                                "transfer_direction": "TO_ROBOT",
                                "item_id": "med_acetaminophen_500",
                                "quantity": 2,
                                "robot_slot_id": "robot_slot_a1",
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

    assert manipulation_client.calls == [
        {
            "action_name": "/ropi/arm/arm1/execute_manipulation",
            "goal": {
                "task_id": "task_delivery_001",
                "transfer_direction": "TO_ROBOT",
                "item_id": "med_acetaminophen_500",
                "quantity": 2,
                "robot_slot_id": "robot_slot_a1",
            },
        }
    ]
    assert response == {
        "ok": True,
        "payload": {
            "accepted": True,
            "goal_handle_id": "goal_handle_manipulation",
        },
    }
