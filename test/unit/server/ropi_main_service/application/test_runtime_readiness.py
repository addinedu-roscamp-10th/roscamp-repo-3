import asyncio

from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.application.runtime_readiness import RosRuntimeReadinessService


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
        return {"ready": True, "checks": []}


class FakeAsyncCommandClient:
    def __init__(self):
        self.calls = []

    def send_command(self, command, payload, timeout=None):
        raise AssertionError("async_get_status should not use sync send_command")

    async def async_send_command(self, command, payload, timeout=None):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {"ready": True, "checks": []}


def test_runtime_readiness_uses_delivery_runtime_config():
    command_client = FakeCommandClient()
    service = RosRuntimeReadinessService(
        command_client=command_client,
        runtime_config=DeliveryRuntimeConfig(
            pinky_id="pinky9",
            pickup_arm_id="arm7",
            destination_arm_id="arm8",
        ),
    )

    response = service.get_status()

    assert response == {"ready": True, "checks": []}
    assert command_client.calls == [
        {
            "command": "get_runtime_status",
            "payload": {
                "pinky_id": "pinky9",
                "arm_ids": ["arm7", "arm8"],
            },
            "timeout": 2.0,
        }
    ]


def test_async_runtime_readiness_uses_async_ros_service_command_client():
    command_client = FakeAsyncCommandClient()
    service = RosRuntimeReadinessService(
        command_client=command_client,
        runtime_config=DeliveryRuntimeConfig(
            pinky_id="pinky9",
            pickup_arm_id="arm7",
            destination_arm_id="arm8",
        ),
    )

    response = asyncio.run(service.async_get_status())

    assert response == {"ready": True, "checks": []}
    assert command_client.calls == [
        {
            "command": "get_runtime_status",
            "payload": {
                "pinky_id": "pinky9",
                "arm_ids": ["arm7", "arm8"],
            },
            "timeout": 2.0,
        }
    ]
