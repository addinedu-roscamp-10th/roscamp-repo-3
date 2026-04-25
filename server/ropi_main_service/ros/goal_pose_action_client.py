from server.ropi_main_service.ros.action_client_base import BaseRclpyActionClient


class RclpyGoalPoseActionClient(BaseRclpyActionClient):

    @staticmethod
    def _load_default_action_type():
        try:
            from ropi_interface.action import NavigateToGoal
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "ropi_interface.action.NavigateToGoal 를 불러올 수 없습니다. "
                "ROS workspace를 build/source 했는지 확인하세요."
            ) from exc

        return NavigateToGoal
