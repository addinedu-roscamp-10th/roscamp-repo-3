import logging
import time

from server.ropi_main_service.application.delivery_config import (
    DEFAULT_DELIVERY_DESTINATION_ARM_ID,
    DEFAULT_DELIVERY_NAVIGATION_TIMEOUT_SEC as DEFAULT_RUNTIME_DELIVERY_NAVIGATION_TIMEOUT_SEC,
    DEFAULT_DELIVERY_PICKUP_ARM_ID,
    get_delivery_runtime_config,
)
from server.ropi_main_service.observability import log_event


PICKUP_ARM_ID = DEFAULT_DELIVERY_PICKUP_ARM_ID
DESTINATION_ARM_ID = DEFAULT_DELIVERY_DESTINATION_ARM_ID
PICKUP_TRANSFER_DIRECTION = "TO_ROBOT"
UNLOAD_TRANSFER_DIRECTION = "FROM_ROBOT"
logger = logging.getLogger(__name__)


class DeliveryOrchestrator:
    DEFAULT_DELIVERY_NAVIGATION_TIMEOUT_SEC = DEFAULT_RUNTIME_DELIVERY_NAVIGATION_TIMEOUT_SEC

    def __init__(
        self,
        *,
        goal_pose_navigation_service,
        manipulation_command_service,
        pickup_goal_pose_resolver,
        destination_goal_pose_resolver,
        return_to_dock_goal_pose_resolver,
        runtime_config=None,
        delivery_navigation_timeout_sec=None,
    ):
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self.goal_pose_navigation_service = goal_pose_navigation_service
        self.manipulation_command_service = manipulation_command_service
        self.pickup_goal_pose_resolver = pickup_goal_pose_resolver
        self.destination_goal_pose_resolver = destination_goal_pose_resolver
        self.return_to_dock_goal_pose_resolver = return_to_dock_goal_pose_resolver
        self.delivery_navigation_timeout_sec = (
            self.runtime_config.navigation_timeout_sec
            if delivery_navigation_timeout_sec is None
            else delivery_navigation_timeout_sec
        )

    def run(self, *, task_id, item_id, quantity, destination_id):
        started_at = time.monotonic()
        log_event(
            logger,
            logging.INFO,
            "delivery_workflow_started",
            task_id=task_id,
            item_id=item_id,
            quantity=quantity,
            destination_id=destination_id,
        )
        pickup_goal_pose = self.pickup_goal_pose_resolver()
        if not pickup_goal_pose:
            response = self._failed(
                "pickup goal pose를 찾을 수 없습니다.",
                reason_code="PICKUP_GOAL_POSE_MISSING",
            )
            self._log_failure("delivery_pickup_goal_pose_missing", task_id, response, started_at)
            return response

        pickup_response = self.goal_pose_navigation_service.navigate(
            task_id=task_id,
            nav_phase="DELIVERY_PICKUP",
            goal_pose=pickup_goal_pose,
            timeout_sec=self.delivery_navigation_timeout_sec,
        )
        if not self._is_success(pickup_response):
            self._log_failure("delivery_pickup_navigation_failed", task_id, pickup_response, started_at)
            return pickup_response

        load_response = self.manipulation_command_service.execute(
            arm_id=self.runtime_config.pickup_arm_id,
            task_id=task_id,
            transfer_direction=PICKUP_TRANSFER_DIRECTION,
            item_id=item_id,
            quantity=quantity,
        )
        if not self._is_success(load_response):
            self._log_failure("delivery_load_failed", task_id, load_response, started_at)
            return load_response

        destination_goal_pose = self.destination_goal_pose_resolver(destination_id)
        if not destination_goal_pose:
            response = self._failed(
                "destination goal pose를 찾을 수 없습니다.",
                reason_code="DESTINATION_GOAL_POSE_MISSING",
            )
            self._log_failure("delivery_destination_goal_pose_missing", task_id, response, started_at)
            return response

        destination_response = self.goal_pose_navigation_service.navigate(
            task_id=task_id,
            nav_phase="DELIVERY_DESTINATION",
            goal_pose=destination_goal_pose,
            timeout_sec=self.delivery_navigation_timeout_sec,
        )
        if not self._is_success(destination_response):
            self._log_failure("delivery_destination_navigation_failed", task_id, destination_response, started_at)
            return destination_response

        unload_response = self.manipulation_command_service.execute(
            arm_id=self.runtime_config.destination_arm_id,
            task_id=task_id,
            transfer_direction=UNLOAD_TRANSFER_DIRECTION,
            item_id=item_id,
            quantity=quantity,
        )
        if not self._is_success(unload_response):
            self._log_failure("delivery_unload_failed", task_id, unload_response, started_at)
            return unload_response

        return_to_dock_goal_pose = self.return_to_dock_goal_pose_resolver()
        if not return_to_dock_goal_pose:
            response = self._failed(
                "return_to_dock goal pose를 찾을 수 없습니다.",
                reason_code="RETURN_TO_DOCK_GOAL_POSE_MISSING",
            )
            self._log_failure("delivery_return_to_dock_goal_pose_missing", task_id, response, started_at)
            return response

        return_to_dock_response = self.goal_pose_navigation_service.navigate(
            task_id=task_id,
            nav_phase="RETURN_TO_DOCK",
            goal_pose=return_to_dock_goal_pose,
            timeout_sec=self.delivery_navigation_timeout_sec,
        )
        if not self._is_success(return_to_dock_response):
            self._log_failure("delivery_return_to_dock_failed", task_id, return_to_dock_response, started_at)
            return return_to_dock_response

        log_event(
            logger,
            logging.INFO,
            "delivery_workflow_succeeded",
            task_id=task_id,
            result_code=return_to_dock_response.get("result_code"),
            elapsed_ms=round((time.monotonic() - started_at) * 1000, 2),
        )
        return return_to_dock_response

    @staticmethod
    def _is_success(response) -> bool:
        return str((response or {}).get("result_code") or "").upper() == "SUCCESS"

    @staticmethod
    def _failed(result_message: str, *, reason_code: str):
        return {
            "result_code": "FAILED",
            "result_message": result_message,
            "reason_code": reason_code,
        }

    @staticmethod
    def _log_failure(event: str, task_id: str, response: dict, started_at: float):
        log_event(
            logger,
            logging.WARNING,
            event,
            task_id=task_id,
            result_code=response.get("result_code"),
            result_message=response.get("result_message"),
            reason_code=response.get("reason_code"),
            elapsed_ms=round((time.monotonic() - started_at) * 1000, 2),
        )


__all__ = [
    "DESTINATION_ARM_ID",
    "DeliveryOrchestrator",
    "PICKUP_ARM_ID",
]
