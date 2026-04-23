import pytest

from server.ropi_main_service.application.manipulation_command import (
    FIXED_PHASE1_ROBOT_SLOT_ID,
    ManipulationCommandService,
)


class FakeCommandClient:
    def __init__(self):
        self.calls = []

    def send_command(self, command, payload):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
            }
        )
        return {
            "accepted": True,
            "goal_handle_id": "goal_handle_001",
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
        "accepted": True,
        "goal_handle_id": "goal_handle_001",
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
        }
    ]


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
