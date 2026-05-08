import asyncio

from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.application.guide_runtime import DEFAULT_GUIDE_PINKY_ID
from server.ropi_main_service.application.runtime_readiness import (
    RosRuntimeReadinessService,
)


GUIDE_COMMAND_RUNTIME_PREFLIGHT_TIMEOUT_SEC = 1.0


class GuideCommandRuntimePreflight:
    def __init__(
        self,
        *,
        readiness_service_factory=RosRuntimeReadinessService,
        readiness_timeout_sec=GUIDE_COMMAND_RUNTIME_PREFLIGHT_TIMEOUT_SEC,
        default_pinky_id=DEFAULT_GUIDE_PINKY_ID,
    ):
        self.readiness_service_factory = readiness_service_factory
        self.readiness_timeout_sec = float(readiness_timeout_sec)
        self.default_pinky_id = str(default_pinky_id).strip() or DEFAULT_GUIDE_PINKY_ID

    def check(self, *, task_id, pinky_id=None):
        target_pinky_id = self._resolve_pinky_id(pinky_id)
        try:
            runtime_status = self._build_readiness_service(
                pinky_id=target_pinky_id,
            ).get_status()
        except Exception as exc:
            runtime_status = self._build_runtime_status_error(exc)
        return self._build_response(
            task_id=task_id,
            pinky_id=target_pinky_id,
            runtime_status=runtime_status,
        )

    async def async_check(self, *, task_id, pinky_id=None):
        target_pinky_id = self._resolve_pinky_id(pinky_id)
        try:
            readiness_service = self._build_readiness_service(pinky_id=target_pinky_id)
            async_get_status = getattr(readiness_service, "async_get_status", None)
            if async_get_status is not None:
                runtime_status = await async_get_status()
            else:
                runtime_status = await asyncio.to_thread(readiness_service.get_status)
        except Exception as exc:
            runtime_status = self._build_runtime_status_error(exc)
        return self._build_response(
            task_id=task_id,
            pinky_id=target_pinky_id,
            runtime_status=runtime_status,
        )

    def _build_readiness_service(self, *, pinky_id):
        return self.readiness_service_factory(
            runtime_config=DeliveryRuntimeConfig(pinky_id=pinky_id),
            arm_ids=[],
            include_navigation=False,
            include_guide=True,
            readiness_timeout_sec=self.readiness_timeout_sec,
        )

    def _build_response(self, *, task_id, pinky_id, runtime_status):
        endpoint = self._build_guide_command_endpoint(pinky_id)
        if self.runtime_ready(runtime_status, pinky_id=pinky_id):
            return {
                "result_code": "ACCEPTED",
                "result_message": "안내 ROS 런타임이 준비되었습니다.",
                "ready": True,
                "task_id": task_id,
                "pinky_id": pinky_id,
                "guide_command_endpoint": endpoint,
                "runtime_status": runtime_status,
            }

        result_message = "안내 ROS 런타임이 준비되지 않았습니다."
        error = ""
        if isinstance(runtime_status, dict):
            error = str(runtime_status.get("error") or "").strip()
        if error:
            result_message = f"{result_message} ({error})"

        return {
            "result_code": "REJECTED",
            "result_message": result_message,
            "reason_code": "GUIDE_RUNTIME_NOT_READY",
            "ready": False,
            "task_id": task_id,
            "pinky_id": pinky_id,
            "guide_command_endpoint": endpoint,
            "runtime_status": runtime_status,
        }

    @classmethod
    def runtime_ready(cls, runtime_status, *, pinky_id):
        if not isinstance(runtime_status, dict):
            return False

        checks = runtime_status.get("checks")
        if not isinstance(checks, list):
            return False

        endpoint = cls._build_guide_command_endpoint(pinky_id)
        for check in checks:
            if not isinstance(check, dict):
                continue
            if check.get("service_name") == endpoint:
                return check.get("ready") is True
        return False

    @staticmethod
    def _build_runtime_status_error(exc):
        return {
            "ready": False,
            "checks": [],
            "error": str(exc),
        }

    @staticmethod
    def _build_guide_command_endpoint(pinky_id):
        return f"/ropi/control/{pinky_id}/guide_command"

    def _resolve_pinky_id(self, pinky_id):
        return str(pinky_id or self.default_pinky_id).strip() or self.default_pinky_id


__all__ = [
    "GUIDE_COMMAND_RUNTIME_PREFLIGHT_TIMEOUT_SEC",
    "GuideCommandRuntimePreflight",
]
