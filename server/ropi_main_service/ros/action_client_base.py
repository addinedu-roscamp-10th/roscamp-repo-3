import threading


class BaseRclpyActionClient:
    def __init__(
        self,
        *,
        node,
        action_type_loader=None,
        action_client_factory=None,
        server_wait_timeout_sec=1.0,
        goal_response_wait_timeout_sec=5.0,
    ):
        self.node = node
        self.action_type_loader = action_type_loader or self._load_default_action_type
        self.action_client_factory = action_client_factory or self._load_default_action_client_factory()
        self.server_wait_timeout_sec = server_wait_timeout_sec
        self.goal_response_wait_timeout_sec = goal_response_wait_timeout_sec

    def send_goal(self, *, action_name, goal, result_wait_timeout_sec=None):
        action_type = self.action_type_loader()
        action_client = self.action_client_factory(self.node, action_type, action_name)

        if not action_client.wait_for_server(timeout_sec=self.server_wait_timeout_sec):
            raise RuntimeError(f"{action_name} action server is not available.")

        goal_msg = self._build_goal_message(action_type, goal)
        send_goal_future = action_client.send_goal_async(goal_msg)
        goal_handle = self._wait_for_future(
            send_goal_future,
            timeout_sec=self.goal_response_wait_timeout_sec,
            error_message=f"{action_name} goal response timed out.",
        )

        if not getattr(goal_handle, "accepted", False):
            return {
                "accepted": False,
                "result_code": "REJECTED",
                "result_message": f"{action_name} goal was rejected.",
            }

        result_future = goal_handle.get_result_async()
        result_wrapper = self._wait_for_future(
            result_future,
            timeout_sec=result_wait_timeout_sec,
            error_message=f"{action_name} action result timed out.",
        )
        response = {
            "accepted": True,
            "status": getattr(result_wrapper, "status", None),
        }
        response.update(self._message_to_dict(getattr(result_wrapper, "result", None)))
        return response

    def is_server_ready(self, *, action_name, wait_timeout_sec=0.0):
        action_type = self.action_type_loader()
        action_client = self.action_client_factory(self.node, action_type, action_name)
        return bool(action_client.wait_for_server(timeout_sec=wait_timeout_sec))

    @classmethod
    def _build_goal_message(cls, action_type, goal):
        goal_msg = action_type.Goal()
        cls._assign_attributes(goal_msg, goal)
        return goal_msg

    @classmethod
    def _assign_attributes(cls, target, values):
        for field_name, field_value in values.items():
            current_value = getattr(target, field_name)

            if isinstance(field_value, dict):
                cls._assign_attributes(current_value, field_value)
                continue

            setattr(target, field_name, field_value)

    @classmethod
    def _message_to_dict(cls, value):
        if value is None:
            return {}

        if isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, dict):
            return {key: cls._message_to_dict(item) for key, item in value.items()}

        if isinstance(value, (list, tuple)):
            return [cls._message_to_dict(item) for item in value]

        field_names = None

        if hasattr(value, "get_fields_and_field_types"):
            field_names = value.get_fields_and_field_types().keys()
        elif hasattr(value, "_fields_and_field_types"):
            field_names = value._fields_and_field_types.keys()
        elif hasattr(type(value), "__slots__") and type(value).__slots__:
            field_names = [slot[1:] if slot.startswith("_") else slot for slot in type(value).__slots__]
        elif hasattr(value, "__dict__"):
            field_names = value.__dict__.keys()

        if field_names is None:
            return value

        result = {}
        for field_name in field_names:
            public_name = field_name[1:] if field_name.startswith("_") else field_name
            if not hasattr(value, public_name):
                continue
            result[public_name] = cls._message_to_dict(getattr(value, public_name))
        return result

    @staticmethod
    def _wait_for_future(future, *, timeout_sec, error_message):
        completed = threading.Event()
        holder = {}

        def _complete(done_future):
            holder["future"] = done_future
            completed.set()

        future.add_done_callback(_complete)

        if not completed.wait(timeout_sec):
            raise RuntimeError(error_message)

        done_future = holder["future"]
        try:
            return done_future.result()
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(str(exc)) from exc

    @staticmethod
    def _load_default_action_client_factory():
        from rclpy.action import ActionClient

        return ActionClient

    @staticmethod
    def _load_default_action_type():
        raise NotImplementedError
