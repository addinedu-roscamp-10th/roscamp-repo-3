import asyncio

from server.ropi_main_service.application.delivery_config import (
    DEFAULT_DELIVERY_DESTINATION_ARM_ID,
    DEFAULT_DELIVERY_PICKUP_ARM_ID,
    DEFAULT_DELIVERY_PINKY_ID,
    get_delivery_runtime_config,
)
from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


FIXED_DELIVERY_PINKY_ID = DEFAULT_DELIVERY_PINKY_ID
FIXED_PHASE1_ARM_IDS = (DEFAULT_DELIVERY_PICKUP_ARM_ID, DEFAULT_DELIVERY_DESTINATION_ARM_ID)
DEFAULT_READINESS_TIMEOUT_SEC = 2.0


class RosRuntimeReadinessService:
    def __init__(
        self,
        *,
        command_client=None,
        runtime_config=None,
        readiness_timeout_sec=DEFAULT_READINESS_TIMEOUT_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self.readiness_timeout_sec = float(readiness_timeout_sec)

    def get_status(self):
        return self.command_client.send_command(
            "get_runtime_status",
            {
                "pinky_id": self.runtime_config.pinky_id,
                "arm_ids": list(self.runtime_config.arm_ids),
            },
            timeout=self.readiness_timeout_sec,
        )

    async def async_get_status(self):
        payload = {
            "pinky_id": self.runtime_config.pinky_id,
            "arm_ids": list(self.runtime_config.arm_ids),
        }
        async_send_command = getattr(self.command_client, "async_send_command", None)

        if async_send_command is not None:
            return await async_send_command(
                "get_runtime_status",
                payload,
                timeout=self.readiness_timeout_sec,
            )

        return await asyncio.to_thread(
            self.command_client.send_command,
            "get_runtime_status",
            payload,
            timeout=self.readiness_timeout_sec,
        )


__all__ = ["RosRuntimeReadinessService"]
