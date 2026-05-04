import asyncio
import logging

from server.ropi_main_service.application.delivery_config import DeliveryRuntimeConfig
from server.ropi_main_service.application.goal_pose_navigation import (
    GoalPoseNavigationService,
)
from server.ropi_main_service.application.guide_runtime import DEFAULT_GUIDE_PINKY_ID
from server.ropi_main_service.application.runtime_readiness import RosRuntimeReadinessService
from server.ropi_main_service.application.workflow_task_manager import (
    get_default_workflow_task_manager,
)
from server.ropi_main_service.observability import log_event


GUIDE_DESTINATION_NAV_PHASE = "GUIDE_DESTINATION"
GUIDE_RUNTIME_READINESS_TIMEOUT_SEC = 1.0
logger = logging.getLogger(__name__)


class GuideNavigationRuntimeStarter:
    def __init__(
        self,
        *,
        workflow_task_manager=None,
        readiness_service_factory=RosRuntimeReadinessService,
        navigation_service_factory=GoalPoseNavigationService,
        readiness_timeout_sec=GUIDE_RUNTIME_READINESS_TIMEOUT_SEC,
        default_pinky_id=DEFAULT_GUIDE_PINKY_ID,
    ):
        self.workflow_task_manager = workflow_task_manager or get_default_workflow_task_manager()
        self.readiness_service_factory = readiness_service_factory
        self.navigation_service_factory = navigation_service_factory
        self.readiness_timeout_sec = float(readiness_timeout_sec)
        self.default_pinky_id = str(default_pinky_id).strip() or DEFAULT_GUIDE_PINKY_ID

    def __call__(
        self,
        *,
        task_id,
        pinky_id,
        goal_pose,
        timeout_sec,
    ):
        return self.start_destination_navigation(
            task_id=task_id,
            pinky_id=pinky_id,
            goal_pose=goal_pose,
            timeout_sec=timeout_sec,
        )

    def start_destination_navigation(
        self,
        *,
        task_id,
        pinky_id,
        goal_pose,
        timeout_sec,
    ):
        target_pinky_id = self._resolve_pinky_id(pinky_id)
        runtime_status = self.get_runtime_readiness_status(pinky_id=target_pinky_id)
        if not self.runtime_ready(runtime_status, pinky_id=target_pinky_id):
            return self.build_runtime_not_ready_response(
                task_id=task_id,
                pinky_id=target_pinky_id,
                runtime_status=runtime_status,
            )

        loop = asyncio.get_running_loop()
        navigation_service = self.navigation_service_factory(
            runtime_config=DeliveryRuntimeConfig(pinky_id=target_pinky_id),
        )
        background_task = self.workflow_task_manager.create_task(
            navigation_service.async_navigate(
                task_id=task_id,
                pinky_id=target_pinky_id,
                nav_phase=GUIDE_DESTINATION_NAV_PHASE,
                goal_pose=goal_pose,
                timeout_sec=timeout_sec,
            ),
            name=f"guide_destination_navigation_{task_id}",
            loop=loop,
            cancel_on_shutdown=True,
        )
        background_task.add_done_callback(
            lambda task: self.handle_navigation_done(task, task_id=task_id)
        )
        return {
            "result_code": "ACCEPTED",
            "result_message": "안내 목적지 이동을 시작했습니다.",
            "navigation_started": True,
            "task_id": task_id,
            "pinky_id": target_pinky_id,
            "nav_phase": GUIDE_DESTINATION_NAV_PHASE,
        }

    def get_runtime_readiness_status(self, *, pinky_id):
        try:
            return self.readiness_service_factory(
                runtime_config=DeliveryRuntimeConfig(pinky_id=pinky_id),
                arm_ids=[],
                include_guide=True,
                readiness_timeout_sec=self.readiness_timeout_sec,
            ).get_status()
        except Exception as exc:
            return {
                "ready": False,
                "checks": [],
                "error": str(exc),
            }

    @staticmethod
    def runtime_ready(runtime_status, *, pinky_id):
        if not isinstance(runtime_status, dict):
            return False

        checks = runtime_status.get("checks")
        if not isinstance(checks, list):
            return False

        required_endpoints = {
            f"/ropi/control/{pinky_id}/navigate_to_goal",
            f"/ropi/control/{pinky_id}/guide_command",
        }
        readiness_by_endpoint = {}
        for check in checks:
            if not isinstance(check, dict):
                continue
            endpoint = check.get("action_name") or check.get("service_name")
            if endpoint in required_endpoints:
                readiness_by_endpoint[endpoint] = check.get("ready") is True

        return all(readiness_by_endpoint.get(endpoint) is True for endpoint in required_endpoints)

    @staticmethod
    def build_runtime_not_ready_response(*, task_id, pinky_id, runtime_status):
        error = ""
        if isinstance(runtime_status, dict):
            error = str(runtime_status.get("error") or "").strip()
        result_message = "안내 ROS 런타임이 준비되지 않았습니다."
        if error:
            result_message = f"{result_message} ({error})"

        return {
            "result_code": "REJECTED",
            "result_message": result_message,
            "reason_code": "GUIDE_RUNTIME_NOT_READY",
            "navigation_started": False,
            "task_id": task_id,
            "pinky_id": pinky_id,
            "nav_phase": GUIDE_DESTINATION_NAV_PHASE,
            "runtime_status": runtime_status,
        }

    @staticmethod
    def handle_navigation_done(task, *, task_id):
        try:
            result = task.result()
        except asyncio.CancelledError:
            log_event(
                logger,
                logging.WARNING,
                "guide_destination_navigation_cancelled",
                task_id=task_id,
                reason_code="GUIDE_NAVIGATION_TASK_CANCELLED",
            )
            return
        except Exception as exc:
            logger.exception(
                "guide destination navigation failed",
                extra={"task_id": task_id, "error": str(exc)},
            )
            return

        log_event(
            logger,
            logging.INFO,
            "guide_destination_navigation_finished",
            task_id=task_id,
            result_code=(result or {}).get("result_code"),
            result_message=(result or {}).get("result_message"),
            reason_code=(result or {}).get("reason_code"),
        )

    def _resolve_pinky_id(self, pinky_id):
        return str(pinky_id or self.default_pinky_id).strip() or self.default_pinky_id


__all__ = [
    "GUIDE_DESTINATION_NAV_PHASE",
    "GUIDE_RUNTIME_READINESS_TIMEOUT_SEC",
    "GuideNavigationRuntimeStarter",
]
