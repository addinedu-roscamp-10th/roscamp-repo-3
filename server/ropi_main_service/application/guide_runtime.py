import asyncio

from server.ropi_main_service.ipc.uds_client import UnixDomainSocketCommandClient


DEFAULT_GUIDE_PINKY_ID = "pinky1"
DEFAULT_GUIDE_RUNTIME_TIMEOUT_SEC = 2.0


class GuideRuntimeService:
    def __init__(
        self,
        *,
        command_client=None,
        default_pinky_id=DEFAULT_GUIDE_PINKY_ID,
        timeout_sec=DEFAULT_GUIDE_RUNTIME_TIMEOUT_SEC,
    ):
        self.command_client = command_client or UnixDomainSocketCommandClient()
        self.default_pinky_id = str(default_pinky_id).strip() or DEFAULT_GUIDE_PINKY_ID
        self.timeout_sec = float(timeout_sec)

    def get_status(self, *, pinky_id=None):
        return self.command_client.send_command(
            "get_runtime_status",
            self._build_payload(pinky_id=pinky_id),
            timeout=self.timeout_sec,
        )

    async def async_get_status(self, *, pinky_id=None):
        payload = self._build_payload(pinky_id=pinky_id)
        async_send_command = getattr(self.command_client, "async_send_command", None)

        if async_send_command is not None:
            return await async_send_command(
                "get_runtime_status",
                payload,
                timeout=self.timeout_sec,
            )

        return await asyncio.to_thread(
            self.command_client.send_command,
            "get_runtime_status",
            payload,
            timeout=self.timeout_sec,
        )

    def _build_payload(self, *, pinky_id=None):
        target_pinky_id = str(pinky_id or self.default_pinky_id).strip() or self.default_pinky_id
        return {
            "pinky_id": target_pinky_id,
            "include_guide": True,
        }


__all__ = ["DEFAULT_GUIDE_PINKY_ID", "GuideRuntimeService"]
