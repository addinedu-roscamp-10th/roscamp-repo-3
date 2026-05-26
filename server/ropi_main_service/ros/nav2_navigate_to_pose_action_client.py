from server.ropi_main_service.ros.action_client_base import BaseRclpyActionClient


GOAL_STATUS_SUCCEEDED = 4
GOAL_STATUS_CANCELED = 5


class RclpyNav2NavigateToPoseActionClient(BaseRclpyActionClient):
    @staticmethod
    def _load_default_action_type():
        try:
            from nav2_msgs.action import NavigateToPose
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "nav2_msgs.action.NavigateToPose 를 불러올 수 없습니다. "
                "Nav2 메시지 패키지를 설치하고 ROS workspace를 source 했는지 확인하세요."
            ) from exc

        return NavigateToPose

    def send_goal(self, *, action_name, goal, result_wait_timeout_sec=None):
        response = super().send_goal(
            action_name=action_name,
            goal=goal,
            result_wait_timeout_sec=result_wait_timeout_sec,
        )
        return self._normalize_nav2_response(response)

    async def async_send_goal(self, *, action_name, goal, result_wait_timeout_sec=None):
        response = await super().async_send_goal(
            action_name=action_name,
            goal=goal,
            result_wait_timeout_sec=result_wait_timeout_sec,
        )
        return self._normalize_nav2_response(response)

    @classmethod
    def _build_goal_message(cls, action_type, goal):
        return super()._build_goal_message(
            action_type,
            {
                "pose": goal.get("pose") or {},
                "behavior_tree": str(goal.get("behavior_tree") or ""),
            },
        )

    @staticmethod
    def _normalize_nav2_response(response):
        response = dict(response or {})
        if "result_code" in response:
            return response

        status = response.get("status")
        error_code = int(response.get("error_code") or 0)
        error_msg = str(response.get("error_msg") or "").strip()

        if status == GOAL_STATUS_SUCCEEDED and error_code == 0:
            response.update(
                {
                    "result_code": "SUCCESS",
                    "result_message": "Nav2 NavigateToPose succeeded.",
                    "reason_code": None,
                }
            )
            return response

        if status == GOAL_STATUS_CANCELED:
            response.update(
                {
                    "result_code": "CANCELLED",
                    "result_message": error_msg or "Nav2 NavigateToPose was cancelled.",
                    "reason_code": "NAV2_GOAL_CANCELLED",
                }
            )
            return response

        response.update(
            {
                "result_code": "FAILED",
                "result_message": error_msg or "Nav2 NavigateToPose failed.",
                "reason_code": f"NAV2_ERROR_{error_code}" if error_code else "NAV2_FAILED",
            }
        )
        return response


__all__ = ["RclpyNav2NavigateToPoseActionClient"]
