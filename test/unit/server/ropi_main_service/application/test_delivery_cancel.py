import asyncio

from server.ropi_main_service.application.task_request import DeliveryRequestService


class FakeCancelCommandClient:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or {
            "result_code": "CANCEL_REQUESTED",
            "result_message": "action cancel request was accepted.",
            "task_id": "101",
            "action_name": None,
            "cancel_requested": True,
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


def test_cancel_delivery_task_sends_cancel_action_to_ros_service():
    command_client = FakeCancelCommandClient()
    service = DeliveryRequestService(command_client=command_client)

    response = service.cancel_delivery_task(task_id="101")

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert command_client.calls == [
        {
            "command": "cancel_action",
            "payload": {
                "task_id": "101",
            },
            "timeout": 5.0,
            "mode": "sync",
        }
    ]


def test_async_cancel_delivery_task_uses_async_ros_service_client():
    command_client = FakeCancelCommandClient()
    service = DeliveryRequestService(command_client=command_client)

    response = asyncio.run(
        service.async_cancel_delivery_task(
            task_id="101",
            action_name="/ropi/control/pinky2/navigate_to_goal",
        )
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert command_client.calls == [
        {
            "command": "cancel_action",
            "payload": {
                "task_id": "101",
                "action_name": "/ropi/control/pinky2/navigate_to_goal",
            },
            "timeout": 5.0,
            "mode": "async",
        }
    ]


def test_cancel_delivery_task_rejects_blank_task_id_without_ros_call():
    command_client = FakeCancelCommandClient()
    service = DeliveryRequestService(command_client=command_client)

    response = service.cancel_delivery_task(task_id="")

    assert response == {
        "result_code": "INVALID_REQUEST",
        "result_message": "task_id가 필요합니다.",
        "reason_code": "TASK_ID_INVALID",
        "task_id": None,
        "task_status": None,
        "assigned_robot_id": None,
    }
    assert command_client.calls == []
