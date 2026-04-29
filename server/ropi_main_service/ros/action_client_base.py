import asyncio
import threading
from datetime import datetime, timezone


class BaseRclpyActionClient:
    def __init__(
        self,
        *,
        node,
        action_type_loader=None,
        action_client_factory=None,
        server_wait_timeout_sec=1.0,
        goal_response_wait_timeout_sec=5.0,
        cancel_wait_timeout_sec=5.0,
    ):
        self.node = node
        self.action_type_loader = action_type_loader or self._load_default_action_type
        self.action_client_factory = action_client_factory or self._load_default_action_client_factory()
        self.server_wait_timeout_sec = server_wait_timeout_sec
        self.goal_response_wait_timeout_sec = goal_response_wait_timeout_sec
        self.cancel_wait_timeout_sec = cancel_wait_timeout_sec
        self._active_goal_handles = {}
        self._active_goal_lock = threading.Lock()
        self._latest_feedback = {}
        self._latest_feedback_lock = threading.Lock()

    def send_goal(self, *, action_name, goal, result_wait_timeout_sec=None):
        action_type = self.action_type_loader()
        action_client = self.action_client_factory(self.node, action_type, action_name)

        if not action_client.wait_for_server(timeout_sec=self.server_wait_timeout_sec):
            raise RuntimeError(f"{action_name} action server is not available.")

        task_id = self._extract_task_id(goal)
        goal_msg = self._build_goal_message(action_type, goal)
        send_goal_future = self._send_goal_async(
            action_client,
            goal_msg,
            feedback_callback=self._build_feedback_callback(
                action_name=action_name,
                task_id=task_id,
            ),
        )
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

        active_key = self._register_active_goal(action_name=action_name, task_id=task_id, goal_handle=goal_handle)
        try:
            result_future = goal_handle.get_result_async()
            result_wrapper = self._wait_for_future(
                result_future,
                timeout_sec=result_wait_timeout_sec,
                error_message=f"{action_name} action result timed out.",
            )
        except RuntimeError:
            if active_key is not None:
                try:
                    self.cancel_goal(task_id=task_id, action_name=action_name)
                except Exception:
                    pass
            raise
        finally:
            if active_key is not None:
                self._unregister_active_goal(active_key)

        response = {
            "accepted": True,
            "status": getattr(result_wrapper, "status", None),
        }
        response.update(self._message_to_dict(getattr(result_wrapper, "result", None)))
        return response

    async def async_send_goal(self, *, action_name, goal, result_wait_timeout_sec=None):
        action_type = self.action_type_loader()
        action_client = self.action_client_factory(self.node, action_type, action_name)

        if not await self._async_wait_for_server(
            action_client,
            timeout_sec=self.server_wait_timeout_sec,
        ):
            raise RuntimeError(f"{action_name} action server is not available.")

        task_id = self._extract_task_id(goal)
        goal_msg = self._build_goal_message(action_type, goal)
        send_goal_future = self._send_goal_async(
            action_client,
            goal_msg,
            feedback_callback=self._build_feedback_callback(
                action_name=action_name,
                task_id=task_id,
            ),
        )
        goal_handle = await self._wait_for_future_async(
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

        active_key = self._register_active_goal(action_name=action_name, task_id=task_id, goal_handle=goal_handle)
        try:
            result_future = goal_handle.get_result_async()
            result_wrapper = await self._wait_for_future_async(
                result_future,
                timeout_sec=result_wait_timeout_sec,
                error_message=f"{action_name} action result timed out.",
            )
        except asyncio.CancelledError:
            if active_key is not None:
                try:
                    await self.async_cancel_goal(task_id=task_id, action_name=action_name)
                except Exception:
                    pass
            raise
        except RuntimeError:
            if active_key is not None:
                try:
                    await self.async_cancel_goal(task_id=task_id, action_name=action_name)
                except Exception:
                    pass
            raise
        finally:
            if active_key is not None:
                self._unregister_active_goal(active_key)

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

    def cancel_goal(self, *, task_id, action_name=None):
        matches = self._find_active_goal_matches(task_id=task_id, action_name=action_name)
        if not matches:
            return self._build_cancel_response(
                result_code="NOT_FOUND",
                result_message="matching active action goal was not found.",
                task_id=task_id,
                action_name=action_name,
                cancel_requested=False,
                matched_goal_count=0,
            )

        details = []
        for _, goal_handle in matches:
            details.append(self._cancel_goal_handle(goal_handle))

        cancel_requested = any(detail.get("cancel_requested") is True for detail in details)
        return self._build_cancel_response(
            result_code="CANCEL_REQUESTED" if cancel_requested else "CANCEL_REJECTED",
            result_message=(
                "action cancel request was accepted."
                if cancel_requested
                else "action cancel request was rejected."
            ),
            task_id=task_id,
            action_name=action_name,
            cancel_requested=cancel_requested,
            matched_goal_count=len(matches),
            details=details,
        )

    async def async_is_server_ready(self, *, action_name, wait_timeout_sec=0.0):
        action_type = self.action_type_loader()
        action_client = self.action_client_factory(self.node, action_type, action_name)
        return bool(
            await self._async_wait_for_server(
                action_client,
                timeout_sec=wait_timeout_sec,
            )
        )

    async def async_cancel_goal(self, *, task_id, action_name=None):
        matches = self._find_active_goal_matches(task_id=task_id, action_name=action_name)
        if not matches:
            return self._build_cancel_response(
                result_code="NOT_FOUND",
                result_message="matching active action goal was not found.",
                task_id=task_id,
                action_name=action_name,
                cancel_requested=False,
                matched_goal_count=0,
            )

        details = []
        for _, goal_handle in matches:
            details.append(await self._async_cancel_goal_handle(goal_handle))

        cancel_requested = any(detail.get("cancel_requested") is True for detail in details)
        return self._build_cancel_response(
            result_code="CANCEL_REQUESTED" if cancel_requested else "CANCEL_REJECTED",
            result_message=(
                "action cancel request was accepted."
                if cancel_requested
                else "action cancel request was rejected."
            ),
            task_id=task_id,
            action_name=action_name,
            cancel_requested=cancel_requested,
            matched_goal_count=len(matches),
            details=details,
        )

    def get_latest_feedback(self, *, task_id, action_name=None):
        normalized_task_id = str(task_id or "").strip()
        normalized_action_name = None if action_name is None else str(action_name).strip()
        if not normalized_task_id:
            return []

        with self._latest_feedback_lock:
            records = [
                self._copy_feedback_record(record)
                for key, record in self._latest_feedback.items()
                if key[1] == normalized_task_id
                and (normalized_action_name is None or key[0] == normalized_action_name)
            ]

        return records

    @classmethod
    def _build_goal_message(cls, action_type, goal):
        goal_msg = action_type.Goal()
        cls._assign_attributes(goal_msg, goal)
        return goal_msg

    @staticmethod
    def _send_goal_async(action_client, goal_msg, *, feedback_callback=None):
        if feedback_callback is None:
            return action_client.send_goal_async(goal_msg)

        try:
            return action_client.send_goal_async(goal_msg, feedback_callback=feedback_callback)
        except TypeError as exc:
            if "feedback_callback" not in str(exc):
                raise
            return action_client.send_goal_async(goal_msg)

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

    def _build_feedback_callback(self, *, action_name, task_id):
        if not task_id:
            return None

        def _on_feedback(feedback_msg):
            self._record_feedback(
                action_name=action_name,
                task_id=task_id,
                feedback_msg=feedback_msg,
            )

        return _on_feedback

    def _record_feedback(self, *, action_name, task_id, feedback_msg):
        payload = self._message_to_dict(getattr(feedback_msg, "feedback", feedback_msg))
        record = {
            "task_id": str(task_id).strip(),
            "action_name": str(action_name).strip(),
            "action_type": self._infer_action_type(action_name=action_name, payload=payload),
            "feedback_type": self._infer_feedback_type(payload),
            "received_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        key = (record["action_name"], record["task_id"])
        with self._latest_feedback_lock:
            self._latest_feedback[key] = record

    @staticmethod
    def _copy_feedback_record(record):
        copied = dict(record)
        payload = copied.get("payload")
        if isinstance(payload, dict):
            copied["payload"] = dict(payload)
        return copied

    @staticmethod
    def _infer_action_type(*, action_name, payload):
        action_name = str(action_name or "")
        if "navigate_to_goal" in action_name or "nav_status" in payload:
            return "navigation"
        if "execute_manipulation" in action_name or "processed_quantity" in payload:
            return "manipulation"
        if "execute_patrol_path" in action_name or "patrol_status" in payload:
            return "patrol"
        return "unknown"

    @staticmethod
    def _infer_feedback_type(payload):
        if "patrol_status" in payload or "current_waypoint_index" in payload:
            return "PATROL_FEEDBACK"
        if "nav_status" in payload or "distance_remaining_m" in payload:
            return "NAVIGATION_FEEDBACK"
        if "processed_quantity" in payload:
            return "MANIPULATION_FEEDBACK"
        return "ACTION_FEEDBACK"

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

    def _cancel_goal_handle(self, goal_handle):
        cancel_goal_async = getattr(goal_handle, "cancel_goal_async", None)
        if cancel_goal_async is None:
            return {
                "cancel_requested": False,
                "result_message": "goal handle does not support cancellation.",
            }

        cancel_future = cancel_goal_async()
        cancel_response = self._wait_for_future(
            cancel_future,
            timeout_sec=self.cancel_wait_timeout_sec,
            error_message="action cancel response timed out.",
        )
        return self._normalize_cancel_result(cancel_response)

    @classmethod
    async def _wait_for_future_async(cls, future, *, timeout_sec, error_message):
        loop = asyncio.get_running_loop()
        asyncio_future = loop.create_future()

        def _complete(done_future):
            def _set_result():
                if asyncio_future.done():
                    return
                try:
                    asyncio_future.set_result(done_future.result())
                except Exception as exc:  # pragma: no cover
                    asyncio_future.set_exception(RuntimeError(str(exc)))

            loop.call_soon_threadsafe(_set_result)

        future.add_done_callback(_complete)

        try:
            return await asyncio.wait_for(asyncio_future, timeout=timeout_sec)
        except asyncio.TimeoutError as exc:
            raise RuntimeError(error_message) from exc

    async def _async_cancel_goal_handle(self, goal_handle):
        cancel_goal_async = getattr(goal_handle, "cancel_goal_async", None)
        if cancel_goal_async is None:
            return {
                "cancel_requested": False,
                "result_message": "goal handle does not support cancellation.",
            }

        cancel_future = cancel_goal_async()
        cancel_response = await self._wait_for_future_async(
            cancel_future,
            timeout_sec=self.cancel_wait_timeout_sec,
            error_message="action cancel response timed out.",
        )
        return self._normalize_cancel_result(cancel_response)

    @staticmethod
    async def _async_wait_for_server(action_client, *, timeout_sec):
        server_is_ready = getattr(action_client, "server_is_ready", None)
        if server_is_ready is None:
            return await asyncio.to_thread(
                action_client.wait_for_server,
                timeout_sec=timeout_sec,
            )

        if timeout_sec is not None and float(timeout_sec) <= 0:
            return bool(server_is_ready())

        loop = asyncio.get_running_loop()
        deadline = None if timeout_sec is None else loop.time() + float(timeout_sec)

        while True:
            if server_is_ready():
                return True

            if deadline is not None:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return False
                await asyncio.sleep(min(0.05, remaining))
                continue

            await asyncio.sleep(0.05)

    @staticmethod
    def _extract_task_id(goal):
        if not isinstance(goal, dict):
            return None

        task_id = str(goal.get("task_id") or "").strip()
        return task_id or None

    def _register_active_goal(self, *, action_name, task_id, goal_handle):
        if not task_id:
            return None

        key = (str(action_name).strip(), task_id)
        with self._active_goal_lock:
            self._active_goal_handles[key] = goal_handle
        return key

    def _unregister_active_goal(self, key):
        with self._active_goal_lock:
            self._active_goal_handles.pop(key, None)

    def _find_active_goal_matches(self, *, task_id, action_name=None):
        normalized_task_id = str(task_id or "").strip()
        normalized_action_name = None if action_name is None else str(action_name).strip()
        if not normalized_task_id:
            return []

        with self._active_goal_lock:
            return [
                (key, goal_handle)
                for key, goal_handle in self._active_goal_handles.items()
                if key[1] == normalized_task_id
                and (normalized_action_name is None or key[0] == normalized_action_name)
            ]

    @staticmethod
    def _normalize_cancel_result(cancel_response):
        goals_canceling = getattr(cancel_response, "goals_canceling", None)
        if goals_canceling is None:
            return {
                "cancel_requested": True,
            }

        return {
            "cancel_requested": bool(goals_canceling),
            "goals_canceling_count": len(goals_canceling),
        }

    @staticmethod
    def _build_cancel_response(
        *,
        result_code,
        result_message,
        task_id,
        action_name,
        cancel_requested,
        matched_goal_count,
        details=None,
    ):
        response = {
            "result_code": result_code,
            "result_message": result_message,
            "task_id": str(task_id or "").strip(),
            "action_name": action_name,
            "cancel_requested": cancel_requested,
            "matched_goal_count": matched_goal_count,
        }

        if details is not None:
            response["details"] = details

        return response

    @staticmethod
    def _load_default_action_client_factory():
        from rclpy.action import ActionClient

        return ActionClient

    @staticmethod
    def _load_default_action_type():
        raise NotImplementedError
