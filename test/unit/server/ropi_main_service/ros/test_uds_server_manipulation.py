import asyncio

from server.ropi_main_service.ipc.uds_protocol import decode_message_bytes, encode_message
from server.ropi_main_service.ros.uds_server import RosServiceUdsServer


class FakeGoalPoseActionClient:
    def send_goal(self, *, action_name, goal, result_wait_timeout_sec=None):
        return {
            "accepted": True,
            "status": 4,
            "result_code": "SUCCESS",
            "result_message": "navigation done",
        }


class FakeManipulationActionClient:
    def __init__(self):
        self.calls = []

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
            "result_message": "manipulation done",
            "processed_quantity": 2,
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
            "result_wait_timeout_sec": 30.0,
        }
    ]
    assert response == {
        "ok": True,
        "payload": {
            "accepted": True,
            "status": 4,
            "result_code": "SUCCESS",
            "result_message": "manipulation done",
            "processed_quantity": 2,
        },
    }
