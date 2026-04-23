class RclpyGoalPoseActionClient:
    def __init__(
        self,
        *,
        node,
        action_type_loader=None,
        action_client_factory=None,
        server_wait_timeout_sec=1.0,
    ):
        self.node = node
        self.action_type_loader = action_type_loader or self._load_default_action_type
        self.action_client_factory = action_client_factory or self._load_default_action_client_factory()
        self.server_wait_timeout_sec = server_wait_timeout_sec

    def send_goal(self, *, action_name, goal):
        action_type = self.action_type_loader()
        action_client = self.action_client_factory(self.node, action_type, action_name)

        if not action_client.wait_for_server(timeout_sec=self.server_wait_timeout_sec):
            raise RuntimeError(f"{action_name} action server is not available.")

        goal_msg = self._build_goal_message(action_type, goal)
        send_goal_future = action_client.send_goal_async(goal_msg)

        return {
            "submitted": True,
            "send_goal_future": send_goal_future,
        }

    @staticmethod
    def _build_goal_message(action_type, goal):
        goal_msg = action_type.Goal()
        RclpyGoalPoseActionClient._assign_attributes(goal_msg, goal)
        return goal_msg

    @staticmethod
    def _assign_attributes(target, values):
        for field_name, field_value in values.items():
            current_value = getattr(target, field_name)

            if isinstance(field_value, dict):
                RclpyGoalPoseActionClient._assign_attributes(current_value, field_value)
                continue

            setattr(target, field_name, field_value)

    @staticmethod
    def _load_default_action_client_factory():
        from rclpy.action import ActionClient

        return ActionClient

    @staticmethod
    def _load_default_action_type():
        try:
            from pinky_interfaces.action import NavigateToGoal
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pinky_interfaces.action.NavigateToGoal 를 불러올 수 없습니다. "
                "ROS workspace를 build/source 했는지 확인하세요."
            ) from exc

        return NavigateToGoal
