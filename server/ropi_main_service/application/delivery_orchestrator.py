PICKUP_ARM_ID = "arm1"
DESTINATION_ARM_ID = "arm2"
PICKUP_TRANSFER_DIRECTION = "TO_ROBOT"
UNLOAD_TRANSFER_DIRECTION = "FROM_ROBOT"


class DeliveryOrchestrator:
    DEFAULT_DELIVERY_NAVIGATION_TIMEOUT_SEC = 120

    def __init__(
        self,
        *,
        goal_pose_navigation_service,
        manipulation_command_service,
        pickup_goal_pose_resolver,
        destination_goal_pose_resolver,
        return_to_dock_goal_pose_resolver,
        delivery_navigation_timeout_sec=DEFAULT_DELIVERY_NAVIGATION_TIMEOUT_SEC,
    ):
        self.goal_pose_navigation_service = goal_pose_navigation_service
        self.manipulation_command_service = manipulation_command_service
        self.pickup_goal_pose_resolver = pickup_goal_pose_resolver
        self.destination_goal_pose_resolver = destination_goal_pose_resolver
        self.return_to_dock_goal_pose_resolver = return_to_dock_goal_pose_resolver
        self.delivery_navigation_timeout_sec = delivery_navigation_timeout_sec

    def run(self, *, task_id, item_id, quantity, destination_id):
        pickup_goal_pose = self.pickup_goal_pose_resolver()
        if not pickup_goal_pose:
            return self._failed(
                "pickup goal pose를 찾을 수 없습니다.",
                reason_code="PICKUP_GOAL_POSE_MISSING",
            )

        pickup_response = self.goal_pose_navigation_service.navigate(
            task_id=task_id,
            nav_phase="DELIVERY_PICKUP",
            goal_pose=pickup_goal_pose,
            timeout_sec=self.delivery_navigation_timeout_sec,
        )
        if not self._is_success(pickup_response):
            return pickup_response

        load_response = self.manipulation_command_service.execute(
            arm_id=PICKUP_ARM_ID,
            task_id=task_id,
            transfer_direction=PICKUP_TRANSFER_DIRECTION,
            item_id=item_id,
            quantity=quantity,
        )
        if not self._is_success(load_response):
            return load_response

        destination_goal_pose = self.destination_goal_pose_resolver(destination_id)
        if not destination_goal_pose:
            return self._failed(
                "destination goal pose를 찾을 수 없습니다.",
                reason_code="DESTINATION_GOAL_POSE_MISSING",
            )

        destination_response = self.goal_pose_navigation_service.navigate(
            task_id=task_id,
            nav_phase="DELIVERY_DESTINATION",
            goal_pose=destination_goal_pose,
            timeout_sec=self.delivery_navigation_timeout_sec,
        )
        if not self._is_success(destination_response):
            return destination_response

        unload_response = self.manipulation_command_service.execute(
            arm_id=DESTINATION_ARM_ID,
            task_id=task_id,
            transfer_direction=UNLOAD_TRANSFER_DIRECTION,
            item_id=item_id,
            quantity=quantity,
        )
        if not self._is_success(unload_response):
            return unload_response

        return_to_dock_goal_pose = self.return_to_dock_goal_pose_resolver()
        if not return_to_dock_goal_pose:
            return self._failed(
                "return_to_dock goal pose를 찾을 수 없습니다.",
                reason_code="RETURN_TO_DOCK_GOAL_POSE_MISSING",
            )

        return self.goal_pose_navigation_service.navigate(
            task_id=task_id,
            nav_phase="RETURN_TO_DOCK",
            goal_pose=return_to_dock_goal_pose,
            timeout_sec=self.delivery_navigation_timeout_sec,
        )

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


__all__ = [
    "DESTINATION_ARM_ID",
    "DeliveryOrchestrator",
    "PICKUP_ARM_ID",
]
