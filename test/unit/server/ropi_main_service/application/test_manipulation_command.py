import asyncio

import pytest

from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.application.manipulation_command import (
    FIXED_PHASE1_ROBOT_SLOT_ID,
    ManipulationCommandService,
)


class FakeCommandClient:
    def __init__(self):
        self.calls = []

    def send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {
            "result_code": "SUCCESS",
            "result_message": "manipulation done",
            "processed_quantity": 2,
        }


class FakeAsyncCommandClient:
    def __init__(self):
        self.calls = []

    def send_command(self, command, payload, timeout=None):
        raise AssertionError("async_execute should not use sync send_command")

    async def async_send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {
            "result_code": "SUCCESS",
            "result_message": "manipulation done",
            "processed_quantity": 2,
        }


def test_execute_sends_if_del_003_command_with_phase1_default_slot_id():
    command_client = FakeCommandClient()
    service = ManipulationCommandService(command_client=command_client)

    response = service.execute(
        arm_id="arm1",
        task_id="task_delivery_001",
        transfer_direction="TO_ROBOT",
        item_id="med_acetaminophen_500",
        quantity=2,
    )

    assert response == {
        "result_code": "SUCCESS",
        "result_message": "manipulation done",
        "processed_quantity": 2,
    }
    assert command_client.calls == [
        {
            "command": "execute_manipulation",
            "payload": {
                "arm_id": "arm1",
                "goal": {
                    "task_id": "task_delivery_001",
                    "transfer_direction": "TO_ROBOT",
                    "item_id": "med_acetaminophen_500",
                    "quantity": 2,
                    "robot_slot_id": FIXED_PHASE1_ROBOT_SLOT_ID,
                },
            },
            "timeout": 30.0,
        }
    ]


def test_async_execute_uses_async_ros_service_command_client():
    command_client = FakeAsyncCommandClient()
    service = ManipulationCommandService(command_client=command_client)

    response = asyncio.run(
        service.async_execute(
            arm_id="arm1",
            task_id="task_delivery_001",
            transfer_direction="TO_ROBOT",
            item_id="med_acetaminophen_500",
            quantity=2,
        )
    )

    assert response["result_code"] == "SUCCESS"
    assert command_client.calls == [
        {
            "command": "execute_manipulation",
            "payload": {
                "arm_id": "arm1",
                "goal": {
                    "task_id": "task_delivery_001",
                    "transfer_direction": "TO_ROBOT",
                    "item_id": "med_acetaminophen_500",
                    "quantity": 2,
                    "robot_slot_id": FIXED_PHASE1_ROBOT_SLOT_ID,
                },
            },
            "timeout": 30.0,
        }
    ]


def test_execute_uses_runtime_config_robot_slot_id():
    command_client = FakeCommandClient()
    service = ManipulationCommandService(
        command_client=command_client,
        runtime_config=DeliveryRuntimeConfig(robot_slot_id="slot_b2"),
    )

    service.execute(
        arm_id="arm1",
        task_id="task_delivery_001",
        transfer_direction="TO_ROBOT",
        item_id="med_acetaminophen_500",
        quantity=2,
    )

    assert command_client.calls[0]["payload"]["goal"]["robot_slot_id"] == "slot_b2"


def test_execute_rejects_invalid_transfer_direction():
    service = ManipulationCommandService(command_client=FakeCommandClient())

    with pytest.raises(ValueError, match="transfer_direction"):
        service.execute(
            arm_id="arm1",
            task_id="task_delivery_001",
            transfer_direction="SIDEWAYS",
            item_id="med_acetaminophen_500",
            quantity=2,
        )
