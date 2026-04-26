from server.ropi_main_service.application.delivery_config import get_delivery_runtime_config


class RosServiceCommandDispatchError(RuntimeError):
    def __init__(self, error_code: str, error: str):
        super().__init__(error)
        self.error_code = error_code


class RosServiceCommandDispatcher:
    DEFAULT_MANIPULATION_RESULT_WAIT_TIMEOUT_SEC = 30.0

    def __init__(
        self,
        *,
        goal_pose_action_client,
        manipulation_action_client=None,
        runtime_config=None,
    ):
        self.goal_pose_action_client = goal_pose_action_client
        self.manipulation_action_client = manipulation_action_client
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self._command_handlers = {
            "get_runtime_status": self._dispatch_get_runtime_status,
            "navigate_to_goal": self._dispatch_navigate_to_goal,
            "execute_manipulation": self._dispatch_execute_manipulation,
        }

    def dispatch(self, command: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        handler = self._command_handlers.get(command)

        if handler is None:
            raise RosServiceCommandDispatchError(
                "UNKNOWN_COMMAND",
                f"Unsupported ROS service command: {command}",
            )

        return handler(payload)

    def _dispatch_navigate_to_goal(self, payload: dict) -> dict:
        pinky_id = self._get_required_identifier(
            payload,
            field_name="pinky_id",
            error_code="PINKY_ID_REQUIRED",
            error_message="navigate_to_goal command requires pinky_id.",
        )
        goal = payload.get("goal") or {}

        return self.goal_pose_action_client.send_goal(
            action_name=f"/ropi/control/{pinky_id}/navigate_to_goal",
            goal=goal,
            result_wait_timeout_sec=self._build_navigation_result_wait_timeout_sec(goal),
        )

    def _dispatch_execute_manipulation(self, payload: dict) -> dict:
        arm_id = self._get_required_identifier(
            payload,
            field_name="arm_id",
            error_code="ARM_ID_REQUIRED",
            error_message="execute_manipulation command requires arm_id.",
        )
        goal = payload.get("goal") or {}
        action_client = self._require_action_client(
            self.manipulation_action_client,
            error_code="MANIPULATION_SERVICE_UNAVAILABLE",
            error_message="execute_manipulation command requires manipulation action client.",
        )

        return action_client.send_goal(
            action_name=f"/ropi/arm/{arm_id}/execute_manipulation",
            goal=goal,
            result_wait_timeout_sec=self.DEFAULT_MANIPULATION_RESULT_WAIT_TIMEOUT_SEC,
        )

    def _dispatch_get_runtime_status(self, payload: dict) -> dict:
        default_pinky_id = self.runtime_config.pinky_id
        pinky_id = str(payload.get("pinky_id") or default_pinky_id).strip() or default_pinky_id
        arm_ids = payload.get("arm_ids") or []
        checks = []

        navigate_action_name = f"/ropi/control/{pinky_id}/navigate_to_goal"
        checks.append(
            {
                "name": f"{pinky_id}.navigate_to_goal",
                "ready": self.goal_pose_action_client.is_server_ready(
                    action_name=navigate_action_name,
                    wait_timeout_sec=0.0,
                ),
                "action_name": navigate_action_name,
            }
        )

        for arm_id in arm_ids:
            action_name = f"/ropi/arm/{arm_id}/execute_manipulation"
            if self.manipulation_action_client is None:
                checks.append(
                    {
                        "name": f"{arm_id}.execute_manipulation",
                        "ready": False,
                        "action_name": action_name,
                        "error": "manipulation action client is not configured",
                    }
                )
                continue

            try:
                ready = self.manipulation_action_client.is_server_ready(
                    action_name=action_name,
                    wait_timeout_sec=0.0,
                )
                checks.append(
                    {
                        "name": f"{arm_id}.execute_manipulation",
                        "ready": ready,
                        "action_name": action_name,
                    }
                )
            except Exception as exc:  # pragma: no cover
                checks.append(
                    {
                        "name": f"{arm_id}.execute_manipulation",
                        "ready": False,
                        "action_name": action_name,
                        "error": str(exc),
                    }
                )

        return {
            "ready": all(check.get("ready") is True for check in checks),
            "checks": checks,
        }

    @staticmethod
    def _get_required_identifier(
        payload: dict,
        *,
        field_name: str,
        error_code: str,
        error_message: str,
    ) -> str:
        value = str(payload.get(field_name) or "").strip()
        if not value:
            raise RosServiceCommandDispatchError(
                error_code,
                error_message,
            )
        return value

    @staticmethod
    def _require_action_client(action_client, *, error_code: str, error_message: str):
        if action_client is None:
            raise RosServiceCommandDispatchError(
                error_code,
                error_message,
            )
        return action_client

    @staticmethod
    def _build_navigation_result_wait_timeout_sec(goal: dict) -> float:
        timeout_sec = float(goal.get("timeout_sec") or 0)
        return max(timeout_sec + 5.0, 30.0)


__all__ = [
    "RosServiceCommandDispatchError",
    "RosServiceCommandDispatcher",
]
