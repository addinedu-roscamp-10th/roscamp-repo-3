import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial

from server.ropi_main_service.application.delivery_config import get_delivery_runtime_config
from server.ropi_main_service.application.manipulation_timeout import (
    DEFAULT_MANIPULATION_ACTION_TIMEOUT_SEC,
    get_manipulation_action_timeout_sec,
)
from server.ropi_main_service.application.patrol_config import get_patrol_runtime_config


class RosServiceCommandDispatchError(RuntimeError):
    def __init__(self, error_code: str, error: str):
        super().__init__(error)
        self.error_code = error_code


@dataclass(frozen=True)
class ActionCommandSpec:
    client_attr: str
    identifier_field: str
    identifier_error_code: str
    identifier_error_message: str
    action_name_template: str
    timeout_strategy: str
    missing_client_error_code: str | None = None
    missing_client_error_message: str | None = None


@dataclass(frozen=True)
class ServiceCommandSpec:
    client_attr: str
    pinky_id_getter: str
    request_builder: str
    service_name_builder: str
    missing_client_error_code: str
    missing_client_error_message: str


@dataclass(frozen=True)
class ActionClientSpec:
    client_attr: str
    client_name: str
    required: bool = False


@dataclass(frozen=True)
class RuntimeStatusContext:
    pinky_id: str
    include_navigation: bool
    include_patrol: bool
    include_guide: bool
    patrol_pinky_id: str
    arm_ids: tuple


@dataclass(frozen=True)
class RuntimeStatusActionTargetSpec:
    client_attr: str
    check_name_template: str
    action_name_template: str


@dataclass(frozen=True)
class RuntimeStatusActionCheck:
    name: str
    action_name: str
    action_client: object | None
    missing_client_error: str | None = None


ACTION_CLIENT_SPECS = (
    ActionClientSpec(
        client_attr="goal_pose_action_client",
        client_name="navigation",
        required=True,
    ),
    ActionClientSpec(
        client_attr="manipulation_action_client",
        client_name="manipulation",
    ),
    ActionClientSpec(
        client_attr="patrol_path_action_client",
        client_name="patrol",
    ),
)

RUNTIME_STATUS_ACTION_TARGET_SPECS = {
    "navigation": RuntimeStatusActionTargetSpec(
        client_attr="goal_pose_action_client",
        check_name_template="{pinky_id}.navigate_to_goal",
        action_name_template="/ropi/control/{pinky_id}/navigate_to_goal",
    ),
    "patrol": RuntimeStatusActionTargetSpec(
        client_attr="patrol_path_action_client",
        check_name_template="{patrol_pinky_id}.execute_patrol_path",
        action_name_template="/ropi/control/{patrol_pinky_id}/execute_patrol_path",
    ),
}


ACTION_COMMAND_SPECS = {
    "navigate_to_goal": ActionCommandSpec(
        client_attr="goal_pose_action_client",
        identifier_field="pinky_id",
        identifier_error_code="PINKY_ID_REQUIRED",
        identifier_error_message="navigate_to_goal command requires pinky_id.",
        action_name_template="/ropi/control/{identifier}/navigate_to_goal",
        timeout_strategy="navigation",
    ),
    "execute_manipulation": ActionCommandSpec(
        client_attr="manipulation_action_client",
        identifier_field="arm_id",
        identifier_error_code="ARM_ID_REQUIRED",
        identifier_error_message="execute_manipulation command requires arm_id.",
        action_name_template="/ropi/arm/{identifier}/execute_manipulation",
        timeout_strategy="manipulation",
        missing_client_error_code="MANIPULATION_SERVICE_UNAVAILABLE",
        missing_client_error_message=(
            "execute_manipulation command requires manipulation action client."
        ),
    ),
    "execute_patrol_path": ActionCommandSpec(
        client_attr="patrol_path_action_client",
        identifier_field="pinky_id",
        identifier_error_code="PINKY_ID_REQUIRED",
        identifier_error_message="execute_patrol_path command requires pinky_id.",
        action_name_template="/ropi/control/{identifier}/execute_patrol_path",
        timeout_strategy="navigation",
        missing_client_error_code="PATROL_SERVICE_UNAVAILABLE",
        missing_client_error_message=(
            "execute_patrol_path command requires patrol path action client."
        ),
    ),
}

SERVICE_COMMAND_SPECS = {
    "fall_response_control": ServiceCommandSpec(
        client_attr="fall_response_control_client",
        pinky_id_getter="_get_fall_response_pinky_id",
        request_builder="_build_fall_response_request",
        service_name_builder="_build_fall_response_service_name",
        missing_client_error_code="FALL_RESPONSE_SERVICE_UNAVAILABLE",
        missing_client_error_message=(
            "fall_response_control command requires fall response service client."
        ),
    ),
    "guide_command": ServiceCommandSpec(
        client_attr="guide_command_client",
        pinky_id_getter="_get_guide_pinky_id",
        request_builder="_build_guide_command_request",
        service_name_builder="_build_guide_command_service_name",
        missing_client_error_code="GUIDE_COMMAND_SERVICE_UNAVAILABLE",
        missing_client_error_message="guide_command requires guide command service client.",
    ),
}


class RosServiceCommandDispatcher:
    DEFAULT_MANIPULATION_RESULT_WAIT_TIMEOUT_SEC = DEFAULT_MANIPULATION_ACTION_TIMEOUT_SEC

    def __init__(
        self,
        *,
        goal_pose_action_client,
        manipulation_action_client=None,
        patrol_path_action_client=None,
        fall_response_control_client=None,
        guide_command_client=None,
        guide_runtime_subscriber=None,
        runtime_config=None,
        patrol_runtime_config=None,
        manipulation_result_wait_timeout_sec=None,
    ):
        self.goal_pose_action_client = goal_pose_action_client
        self.manipulation_action_client = manipulation_action_client
        self.patrol_path_action_client = patrol_path_action_client
        self.fall_response_control_client = fall_response_control_client
        self.guide_command_client = guide_command_client
        self.guide_runtime_subscriber = guide_runtime_subscriber
        self.runtime_config = runtime_config or get_delivery_runtime_config()
        self.patrol_runtime_config = patrol_runtime_config or get_patrol_runtime_config()
        self.manipulation_result_wait_timeout_sec = (
            get_manipulation_action_timeout_sec()
            if manipulation_result_wait_timeout_sec is None
            else float(manipulation_result_wait_timeout_sec)
        )
        self._dispatch_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="ropi_ros_dispatch",
        )
        self._command_handlers = {
            "cancel_action": self._dispatch_cancel_action,
            "get_action_feedback": self._dispatch_get_action_feedback,
            "get_runtime_status": self._dispatch_get_runtime_status,
            **{
                command: partial(self._dispatch_action_command, spec)
                for command, spec in ACTION_COMMAND_SPECS.items()
            },
            **{
                command: partial(self._dispatch_service_command, spec)
                for command, spec in SERVICE_COMMAND_SPECS.items()
            },
        }
        self._async_command_handlers = {
            "cancel_action": self._async_dispatch_cancel_action,
            "get_action_feedback": self._async_dispatch_get_action_feedback,
            "get_runtime_status": self._async_dispatch_get_runtime_status,
            **{
                command: partial(self._async_dispatch_action_command, spec)
                for command, spec in ACTION_COMMAND_SPECS.items()
            },
            **{
                command: partial(self._async_dispatch_service_command, spec)
                for command, spec in SERVICE_COMMAND_SPECS.items()
            },
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

    async def async_dispatch(self, command: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        async_handler = self._async_command_handlers.get(command)

        if async_handler is None:
            raise RosServiceCommandDispatchError(
                "UNKNOWN_COMMAND",
                f"Unsupported ROS service command: {command}",
            )

        return await async_handler(payload)

    def close(self):
        self._dispatch_executor.shutdown(wait=False, cancel_futures=True)

    def _dispatch_navigate_to_goal(self, payload: dict) -> dict:
        return self._dispatch_action_command(
            ACTION_COMMAND_SPECS["navigate_to_goal"],
            payload,
        )

    def _dispatch_execute_manipulation(self, payload: dict) -> dict:
        return self._dispatch_action_command(
            ACTION_COMMAND_SPECS["execute_manipulation"],
            payload,
        )

    def _dispatch_execute_patrol_path(self, payload: dict) -> dict:
        return self._dispatch_action_command(
            ACTION_COMMAND_SPECS["execute_patrol_path"],
            payload,
        )

    def _dispatch_fall_response_control(self, payload: dict) -> dict:
        return self._dispatch_service_command(
            SERVICE_COMMAND_SPECS["fall_response_control"],
            payload,
        )

    def _dispatch_guide_command(self, payload: dict) -> dict:
        return self._dispatch_service_command(
            SERVICE_COMMAND_SPECS["guide_command"],
            payload,
        )

    def _dispatch_action_command(
        self,
        spec: ActionCommandSpec,
        payload: dict,
    ) -> dict:
        identifier = self._get_required_identifier(
            payload,
            field_name=spec.identifier_field,
            error_code=spec.identifier_error_code,
            error_message=spec.identifier_error_message,
        )
        goal = payload.get("goal") or {}
        action_client = self._get_action_client_for_spec(spec)

        return action_client.send_goal(
            action_name=self._build_spec_action_name(spec, identifier),
            goal=goal,
            result_wait_timeout_sec=self._build_spec_result_wait_timeout_sec(
                spec,
                goal,
            ),
        )

    async def _async_dispatch_action_command(
        self,
        spec: ActionCommandSpec,
        payload: dict,
    ) -> dict:
        identifier = self._get_required_identifier(
            payload,
            field_name=spec.identifier_field,
            error_code=spec.identifier_error_code,
            error_message=spec.identifier_error_message,
        )
        goal = payload.get("goal") or {}
        action_client = self._get_action_client_for_spec(spec)

        return await self._async_send_goal(
            action_client,
            action_name=self._build_spec_action_name(spec, identifier),
            goal=goal,
            result_wait_timeout_sec=self._build_spec_result_wait_timeout_sec(
                spec,
                goal,
            ),
        )

    def _dispatch_service_command(
        self,
        spec: ServiceCommandSpec,
        payload: dict,
    ) -> dict:
        pinky_id = getattr(self, spec.pinky_id_getter)(payload)
        request = getattr(self, spec.request_builder)(payload)
        service_client = self._get_service_client_for_spec(spec)
        return service_client.call(
            service_name=getattr(self, spec.service_name_builder)(pinky_id),
            request=request,
        )

    async def _async_dispatch_service_command(
        self,
        spec: ServiceCommandSpec,
        payload: dict,
    ) -> dict:
        pinky_id = getattr(self, spec.pinky_id_getter)(payload)
        request = getattr(self, spec.request_builder)(payload)
        service_client = self._get_service_client_for_spec(spec)
        return await self._async_call_service(
            service_client,
            service_name=getattr(self, spec.service_name_builder)(pinky_id),
            request=request,
        )

    def _get_action_client_for_spec(self, spec: ActionCommandSpec):
        action_client = getattr(self, spec.client_attr)
        if spec.missing_client_error_code is None:
            return action_client

        return self._require_action_client(
            action_client,
            error_code=spec.missing_client_error_code,
            error_message=spec.missing_client_error_message,
        )

    def _get_service_client_for_spec(self, spec: ServiceCommandSpec):
        return self._require_action_client(
            getattr(self, spec.client_attr),
            error_code=spec.missing_client_error_code,
            error_message=spec.missing_client_error_message,
        )

    @staticmethod
    def _build_spec_action_name(spec: ActionCommandSpec, identifier: str) -> str:
        return spec.action_name_template.format(identifier=identifier)

    def _build_spec_result_wait_timeout_sec(
        self,
        spec: ActionCommandSpec,
        goal: dict,
    ) -> float:
        if spec.timeout_strategy == "navigation":
            return self._build_navigation_result_wait_timeout_sec(goal)
        if spec.timeout_strategy == "manipulation":
            return self.manipulation_result_wait_timeout_sec
        raise RosServiceCommandDispatchError(
            "ACTION_TIMEOUT_STRATEGY_UNKNOWN",
            f"Unsupported action timeout strategy: {spec.timeout_strategy}",
        )

    def _dispatch_cancel_action(self, payload: dict) -> dict:
        task_id = self._get_required_identifier(
            payload,
            field_name="task_id",
            error_code="TASK_ID_REQUIRED",
            error_message="cancel_action command requires task_id.",
        )
        action_name = self._get_optional_identifier(payload, "action_name")
        details = [
            self._cancel_goal(
                action_client,
                client_name=spec.client_name,
                task_id=task_id,
                action_name=action_name,
            )
            for spec, action_client in self._iter_action_clients()
        ]

        return self._build_cancel_action_response(
            task_id=task_id,
            action_name=action_name,
            details=details,
        )

    def _dispatch_get_action_feedback(self, payload: dict) -> dict:
        task_id = self._get_required_identifier(
            payload,
            field_name="task_id",
            error_code="TASK_ID_REQUIRED",
            error_message="get_action_feedback command requires task_id.",
        )
        action_name = self._get_optional_identifier(payload, "action_name")
        feedback = []

        for spec, action_client in self._iter_action_clients():
            feedback.extend(
                self._get_latest_feedback(
                    action_client,
                    client_name=spec.client_name,
                    task_id=task_id,
                    action_name=action_name,
                )
            )

        return self._build_action_feedback_response(
            task_id=task_id,
            action_name=action_name,
            feedback=feedback,
        )

    async def _async_dispatch_navigate_to_goal(self, payload: dict) -> dict:
        return await self._async_dispatch_action_command(
            ACTION_COMMAND_SPECS["navigate_to_goal"],
            payload,
        )

    async def _async_dispatch_execute_manipulation(self, payload: dict) -> dict:
        return await self._async_dispatch_action_command(
            ACTION_COMMAND_SPECS["execute_manipulation"],
            payload,
        )

    async def _async_dispatch_execute_patrol_path(self, payload: dict) -> dict:
        return await self._async_dispatch_action_command(
            ACTION_COMMAND_SPECS["execute_patrol_path"],
            payload,
        )

    async def _async_dispatch_fall_response_control(self, payload: dict) -> dict:
        return await self._async_dispatch_service_command(
            SERVICE_COMMAND_SPECS["fall_response_control"],
            payload,
        )

    async def _async_dispatch_guide_command(self, payload: dict) -> dict:
        return await self._async_dispatch_service_command(
            SERVICE_COMMAND_SPECS["guide_command"],
            payload,
        )

    async def _async_dispatch_cancel_action(self, payload: dict) -> dict:
        task_id = self._get_required_identifier(
            payload,
            field_name="task_id",
            error_code="TASK_ID_REQUIRED",
            error_message="cancel_action command requires task_id.",
        )
        action_name = self._get_optional_identifier(payload, "action_name")
        details = []

        for spec, action_client in self._iter_action_clients():
            details.append(
                await self._async_cancel_goal(
                    action_client,
                    client_name=spec.client_name,
                    task_id=task_id,
                    action_name=action_name,
                )
            )

        return self._build_cancel_action_response(
            task_id=task_id,
            action_name=action_name,
            details=details,
        )

    async def _async_dispatch_get_action_feedback(self, payload: dict) -> dict:
        task_id = self._get_required_identifier(
            payload,
            field_name="task_id",
            error_code="TASK_ID_REQUIRED",
            error_message="get_action_feedback command requires task_id.",
        )
        action_name = self._get_optional_identifier(payload, "action_name")
        feedback = []

        for spec, action_client in self._iter_action_clients():
            feedback.extend(
                self._get_latest_feedback(
                    action_client,
                    client_name=spec.client_name,
                    task_id=task_id,
                    action_name=action_name,
                )
            )

        return self._build_action_feedback_response(
            task_id=task_id,
            action_name=action_name,
            feedback=feedback,
        )

    def _dispatch_get_runtime_status(self, payload: dict) -> dict:
        context = self._build_runtime_status_context(payload)
        checks = [
            self._build_runtime_action_ready_check(check)
            for check in self._iter_runtime_status_action_checks(context)
        ]
        guide_snapshot = None

        if context.include_guide:
            checks.append(self._build_runtime_guide_service_check(context.pinky_id))
            guide_snapshot = self._build_guide_runtime_snapshot(context.pinky_id)

        return self._build_runtime_status_response(checks, guide_snapshot)

    async def _async_dispatch_get_runtime_status(self, payload: dict) -> dict:
        context = self._build_runtime_status_context(payload)
        checks = [
            await self._async_build_runtime_action_ready_check(check)
            for check in self._iter_runtime_status_action_checks(context)
        ]
        guide_snapshot = None

        if context.include_guide:
            checks.append(
                await self._async_build_runtime_guide_service_check(context.pinky_id)
            )
            guide_snapshot = self._build_guide_runtime_snapshot(context.pinky_id)

        return self._build_runtime_status_response(checks, guide_snapshot)

    def _build_runtime_status_context(self, payload: dict) -> RuntimeStatusContext:
        default_pinky_id = self.runtime_config.pinky_id
        pinky_id = (
            str(payload.get("pinky_id") or default_pinky_id).strip()
            or default_pinky_id
        )
        include_navigation = payload.get("include_navigation")
        include_navigation = (
            True if include_navigation is None else bool(include_navigation)
        )
        patrol_pinky_id = (
            str(payload.get("patrol_pinky_id") or pinky_id).strip() or pinky_id
        )
        return RuntimeStatusContext(
            pinky_id=pinky_id,
            include_navigation=include_navigation,
            include_patrol=bool(payload.get("include_patrol")),
            include_guide=bool(payload.get("include_guide")),
            patrol_pinky_id=patrol_pinky_id,
            arm_ids=tuple(payload.get("arm_ids") or ()),
        )

    def _iter_runtime_status_action_checks(self, context: RuntimeStatusContext):
        if context.include_navigation:
            yield self._build_runtime_status_action_target_check(
                RUNTIME_STATUS_ACTION_TARGET_SPECS["navigation"],
                pinky_id=context.pinky_id,
                patrol_pinky_id=context.patrol_pinky_id,
            )

        if context.include_patrol and self.patrol_path_action_client is not None:
            yield self._build_runtime_status_action_target_check(
                RUNTIME_STATUS_ACTION_TARGET_SPECS["patrol"],
                pinky_id=context.pinky_id,
                patrol_pinky_id=context.patrol_pinky_id,
            )

        for arm_id in context.arm_ids:
            yield RuntimeStatusActionCheck(
                name=f"{arm_id}.execute_manipulation",
                action_name=f"/ropi/arm/{arm_id}/execute_manipulation",
                action_client=self.manipulation_action_client,
                missing_client_error="manipulation action client is not configured",
            )

    def _build_runtime_status_action_target_check(
        self,
        spec: RuntimeStatusActionTargetSpec,
        **identifiers,
    ) -> RuntimeStatusActionCheck:
        return RuntimeStatusActionCheck(
            name=spec.check_name_template.format(**identifiers),
            action_name=spec.action_name_template.format(**identifiers),
            action_client=getattr(self, spec.client_attr),
        )

    def _build_runtime_action_ready_check(self, check: RuntimeStatusActionCheck):
        if check.action_client is None:
            return self._build_runtime_action_unavailable_check(check)

        try:
            ready = check.action_client.is_server_ready(
                action_name=check.action_name,
                wait_timeout_sec=0.0,
            )
            return self._build_runtime_action_check_payload(check, ready=ready)
        except Exception as exc:  # pragma: no cover
            return self._build_runtime_action_check_payload(
                check,
                ready=False,
                error=str(exc),
            )

    async def _async_build_runtime_action_ready_check(
        self,
        check: RuntimeStatusActionCheck,
    ):
        if check.action_client is None:
            return self._build_runtime_action_unavailable_check(check)

        try:
            ready = await self._async_is_server_ready(
                check.action_client,
                action_name=check.action_name,
                wait_timeout_sec=0.0,
            )
            return self._build_runtime_action_check_payload(check, ready=ready)
        except Exception as exc:  # pragma: no cover
            return self._build_runtime_action_check_payload(
                check,
                ready=False,
                error=str(exc),
            )

    def _build_runtime_action_unavailable_check(self, check: RuntimeStatusActionCheck):
        return self._build_runtime_action_check_payload(
            check,
            ready=False,
            error=check.missing_client_error,
        )

    @staticmethod
    def _build_runtime_action_check_payload(
        check: RuntimeStatusActionCheck,
        *,
        ready,
        error=None,
    ):
        payload = {
            "name": check.name,
            "ready": ready,
            "action_name": check.action_name,
        }
        if error:
            payload["error"] = error
        return payload

    def _build_runtime_guide_service_check(self, pinky_id: str):
        guide_service_name = self._build_guide_command_service_name(pinky_id)
        if self.guide_command_client is None:
            return self._build_runtime_guide_service_unavailable_check(
                pinky_id,
                guide_service_name,
            )

        try:
            service_client = self.guide_command_client.service_client_factory(
                self.guide_command_client.node,
                self.guide_command_client.service_type_loader(),
                guide_service_name,
            )
            return self._build_runtime_guide_service_check_payload(
                pinky_id,
                guide_service_name,
                ready=service_client.wait_for_service(timeout_sec=0.0),
            )
        except Exception as exc:  # pragma: no cover
            return self._build_runtime_guide_service_check_payload(
                pinky_id,
                guide_service_name,
                ready=False,
                error=str(exc),
            )

    async def _async_build_runtime_guide_service_check(self, pinky_id: str):
        guide_service_name = self._build_guide_command_service_name(pinky_id)
        if self.guide_command_client is None:
            return self._build_runtime_guide_service_unavailable_check(
                pinky_id,
                guide_service_name,
            )

        try:
            service_type = self.guide_command_client.service_type_loader()
            service_client = self.guide_command_client.service_client_factory(
                self.guide_command_client.node,
                service_type,
                guide_service_name,
            )
            return self._build_runtime_guide_service_check_payload(
                pinky_id,
                guide_service_name,
                ready=await self.guide_command_client._async_wait_for_service(
                    service_client,
                    timeout_sec=0.0,
                ),
            )
        except Exception as exc:  # pragma: no cover
            return self._build_runtime_guide_service_check_payload(
                pinky_id,
                guide_service_name,
                ready=False,
                error=str(exc),
            )

    def _build_runtime_guide_service_unavailable_check(
        self,
        pinky_id,
        guide_service_name,
    ):
        return self._build_runtime_guide_service_check_payload(
            pinky_id,
            guide_service_name,
            ready=False,
            error="guide command service client is not configured",
        )

    @staticmethod
    def _build_runtime_guide_service_check_payload(
        pinky_id,
        guide_service_name,
        *,
        ready,
        error=None,
    ):
        payload = {
            "name": f"{pinky_id}.guide_command",
            "ready": ready,
            "service_name": guide_service_name,
        }
        if error:
            payload["error"] = error
        return payload

    @staticmethod
    def _build_runtime_status_response(checks, guide_snapshot):
        return {
            "ready": all(check.get("ready") is True for check in checks),
            "checks": checks,
            "guide_runtime": guide_snapshot,
        }

    async def _async_send_goal(self, action_client, **kwargs):
        async_send_goal = getattr(action_client, "async_send_goal", None)
        if async_send_goal is not None:
            return await async_send_goal(**kwargs)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._dispatch_executor,
            partial(action_client.send_goal, **kwargs),
        )

    async def _async_is_server_ready(self, action_client, **kwargs):
        async_is_server_ready = getattr(action_client, "async_is_server_ready", None)
        if async_is_server_ready is not None:
            return await async_is_server_ready(**kwargs)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._dispatch_executor,
            partial(action_client.is_server_ready, **kwargs),
        )

    async def _async_call_service(self, service_client, **kwargs):
        async_call = getattr(service_client, "async_call", None)
        if async_call is not None:
            return await async_call(**kwargs)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._dispatch_executor,
            partial(service_client.call, **kwargs),
        )

    def _iter_action_clients(self):
        for spec in ACTION_CLIENT_SPECS:
            action_client = getattr(self, spec.client_attr)
            if action_client is None and not spec.required:
                continue
            yield spec, action_client

    def _cancel_goal(self, action_client, *, client_name, **kwargs):
        cancel_goal = getattr(action_client, "cancel_goal", None)
        if cancel_goal is None:
            return {
                "client": client_name,
                "result_code": "UNSUPPORTED",
                "cancel_requested": False,
                "matched_goal_count": 0,
            }

        result = cancel_goal(**kwargs)
        result["client"] = client_name
        return result

    async def _async_cancel_goal(self, action_client, *, client_name, **kwargs):
        async_cancel_goal = getattr(action_client, "async_cancel_goal", None)
        if async_cancel_goal is not None:
            result = await async_cancel_goal(**kwargs)
            result["client"] = client_name
            return result

        cancel_goal = getattr(action_client, "cancel_goal", None)
        if cancel_goal is None:
            return {
                "client": client_name,
                "result_code": "UNSUPPORTED",
                "cancel_requested": False,
                "matched_goal_count": 0,
            }

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            self._dispatch_executor,
            partial(cancel_goal, **kwargs),
        )
        result["client"] = client_name
        return result

    @staticmethod
    def _get_latest_feedback(action_client, *, client_name, **kwargs):
        get_latest_feedback = getattr(action_client, "get_latest_feedback", None)
        if get_latest_feedback is None:
            return []

        feedback_records = get_latest_feedback(**kwargs)
        return [
            {
                "client": client_name,
                **record,
            }
            for record in feedback_records
        ]

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
    def _get_optional_identifier(payload: dict, field_name: str):
        value = str(payload.get(field_name) or "").strip()
        return value or None

    @staticmethod
    def _require_action_client(action_client, *, error_code: str, error_message: str):
        if action_client is None:
            raise RosServiceCommandDispatchError(
                error_code,
                error_message,
            )
        return action_client

    def _build_guide_runtime_snapshot(self, pinky_id: str):
        subscriber = self.guide_runtime_subscriber
        if subscriber is None:
            return {
                "pinky_id": pinky_id,
                "connected": False,
                "stale": True,
                "last_update": None,
                "error": "guide runtime subscriber is not configured",
            }

        latest_updates = subscriber.latest_updates
        update = latest_updates.get(pinky_id)
        if update is None:
            return {
                "pinky_id": pinky_id,
                "connected": False,
                "stale": True,
                "last_update": None,
            }

        return {
            "pinky_id": pinky_id,
            "connected": True,
            "stale": bool(update.stale),
            "last_update": {
                "task_id": update.task_id,
                "pinky_id": update.pinky_id,
                "guide_phase": update.guide_phase,
                "target_track_id": update.target_track_id,
                "reason_code": update.reason_code,
                "seq": update.seq,
                "occurred_at_sec": update.occurred_at_sec,
                "occurred_at_nanosec": update.occurred_at_nanosec,
                "received_at_sec": update.received_at_sec,
                "received_at_nanosec": update.received_at_nanosec,
            },
        }

    @staticmethod
    def _build_navigation_result_wait_timeout_sec(goal: dict) -> float:
        timeout_sec = float(goal.get("timeout_sec") or 0)
        return max(timeout_sec + 5.0, 30.0)

    def _get_fall_response_pinky_id(self, payload: dict) -> str:
        return (
            self._get_optional_identifier(payload, "pinky_id")
            or self.patrol_runtime_config.pinky_id
        )

    def _get_guide_pinky_id(self, payload: dict) -> str:
        return self._get_required_identifier(
            payload,
            field_name="pinky_id",
            error_code="PINKY_ID_REQUIRED",
            error_message="guide_command requires pinky_id.",
        )

    @classmethod
    def _build_fall_response_request(cls, payload: dict) -> dict:
        request = payload.get("request")
        if not isinstance(request, dict):
            request = payload
        task_id = cls._get_required_identifier(
            request,
            field_name="task_id",
            error_code="TASK_ID_REQUIRED",
            error_message="fall_response_control command requires task_id.",
        )
        command_type = cls._get_required_identifier(
            request,
            field_name="command_type",
            error_code="COMMAND_TYPE_REQUIRED",
            error_message="fall_response_control command requires command_type.",
        )
        return {
            "task_id": task_id,
            "command_type": command_type,
        }

    @classmethod
    def _build_guide_command_request(cls, payload: dict) -> dict:
        request = payload.get("request")
        if not isinstance(request, dict):
            request = payload
        task_id = cls._get_required_identifier(
            request,
            field_name="task_id",
            error_code="TASK_ID_REQUIRED",
            error_message="guide_command requires task_id.",
        )
        command_type = cls._get_required_identifier(
            request,
            field_name="command_type",
            error_code="COMMAND_TYPE_REQUIRED",
            error_message="guide_command requires command_type.",
        )
        command_type = command_type.strip().upper()
        if command_type not in {"WAIT_TARGET_TRACKING", "START_GUIDANCE"}:
            raise RosServiceCommandDispatchError(
                "COMMAND_TYPE_INVALID",
                "guide_command supports only WAIT_TARGET_TRACKING or START_GUIDANCE.",
            )

        target_track_raw = request.get("target_track_id", -1)
        try:
            target_track_id = int(str(target_track_raw).strip())
        except (TypeError, ValueError) as exc:
            raise RosServiceCommandDispatchError(
                "TARGET_TRACK_ID_INVALID",
                "guide_command requires integer target_track_id.",
            ) from exc

        destination_id = cls._get_optional_identifier(request, "destination_id") or ""
        destination_pose = request.get("destination_pose") or {}
        if not isinstance(destination_pose, dict):
            raise RosServiceCommandDispatchError(
                "DESTINATION_POSE_INVALID",
                "guide_command requires object destination_pose.",
            )
        if command_type == "START_GUIDANCE":
            if target_track_id < 0:
                raise RosServiceCommandDispatchError(
                    "TARGET_TRACK_ID_REQUIRED",
                    "START_GUIDANCE requires non-negative target_track_id.",
                )
            if not destination_pose:
                raise RosServiceCommandDispatchError(
                    "DESTINATION_POSE_REQUIRED",
                    "START_GUIDANCE requires destination_pose.",
                )

        return {
            "task_id": task_id,
            "command_type": command_type,
            "target_track_id": target_track_id,
            "destination_id": destination_id,
            "destination_pose": destination_pose,
        }

    @staticmethod
    def _build_fall_response_service_name(pinky_id: str) -> str:
        return f"/ropi/control/{pinky_id}/fall_response_control"

    @staticmethod
    def _build_guide_command_service_name(pinky_id: str) -> str:
        return f"/ropi/control/{pinky_id}/guide_command"

    @staticmethod
    def _build_cancel_action_response(*, task_id, action_name, details):
        cancel_requested = any(detail.get("cancel_requested") is True for detail in details)
        return {
            "result_code": "CANCEL_REQUESTED" if cancel_requested else "NOT_FOUND",
            "result_message": (
                "action cancel request was accepted."
                if cancel_requested
                else "matching active action goal was not found."
            ),
            "task_id": task_id,
            "action_name": action_name,
            "cancel_requested": cancel_requested,
            "details": details,
        }

    @staticmethod
    def _build_action_feedback_response(*, task_id, action_name, feedback):
        return {
            "result_code": "FOUND" if feedback else "NOT_FOUND",
            "task_id": task_id,
            "action_name": action_name,
            "feedback": feedback,
        }


__all__ = [
    "ACTION_CLIENT_SPECS",
    "ACTION_COMMAND_SPECS",
    "RUNTIME_STATUS_ACTION_TARGET_SPECS",
    "SERVICE_COMMAND_SPECS",
    "ActionClientSpec",
    "ActionCommandSpec",
    "RosServiceCommandDispatchError",
    "RosServiceCommandDispatcher",
    "RuntimeStatusActionTargetSpec",
    "ServiceCommandSpec",
]
