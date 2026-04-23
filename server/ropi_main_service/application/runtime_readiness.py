from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


FIXED_DELIVERY_PINKY_ID = "pinky2"
FIXED_PHASE1_ARM_IDS = ("arm1", "arm2")
DEFAULT_READINESS_TIMEOUT_SEC = 2.0


class RosRuntimeReadinessService:
    def __init__(
        self,
        *,
        command_client=None,
        readiness_timeout_sec=DEFAULT_READINESS_TIMEOUT_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.readiness_timeout_sec = float(readiness_timeout_sec)

    def get_status(self):
        return self.command_client.send_command(
            "get_runtime_status",
            {
                "pinky_id": FIXED_DELIVERY_PINKY_ID,
                "arm_ids": list(FIXED_PHASE1_ARM_IDS),
            },
            timeout=self.readiness_timeout_sec,
        )


__all__ = ["RosRuntimeReadinessService"]
