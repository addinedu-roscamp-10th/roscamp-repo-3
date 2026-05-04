import asyncio
import inspect
from dataclasses import dataclass


@dataclass(frozen=True)
class RpcDispatchResult:
    ok: bool
    payload: object = None
    error_code: str = ""
    error_message: str = ""


class ControlRpcDispatcher:
    def __init__(
        self,
        *,
        service_registry,
        sync_service_builder=None,
        async_service_builder=None,
        task_update_publisher=None,
        task_monitor_watermark_provider=None,
    ):
        self.service_registry = service_registry
        self.sync_service_builder = sync_service_builder or self._default_service_builder
        self.async_service_builder = async_service_builder or self.sync_service_builder
        self.task_update_publisher = task_update_publisher
        self.task_monitor_watermark_provider = task_monitor_watermark_provider

    def dispatch(self, payload: dict):
        service_name = payload.get("service")
        method_name = payload.get("method")
        kwargs = payload.get("kwargs") or {}
        task_monitor_handoff_seq = self._task_monitor_handoff_seq(
            service_name,
            method_name,
        )

        factory = self.service_registry.get(service_name)
        if factory is None:
            return self._error(
                "UNKNOWN_SERVICE",
                f"지원하지 않는 서비스입니다: {service_name}",
            )

        service = self.sync_service_builder(service_name, factory)
        method = getattr(service, method_name, None)
        if method is None:
            return self._error(
                "UNKNOWN_METHOD",
                f"지원하지 않는 메서드입니다: {service_name}.{method_name}",
            )

        try:
            result = method(**kwargs)
        except Exception as exc:
            return self._error("RPC_ERROR", str(exc))

        result = self._attach_task_monitor_handoff_seq(result, task_monitor_handoff_seq)
        return RpcDispatchResult(ok=True, payload=result)

    async def async_dispatch(self, payload: dict):
        service_name = payload.get("service")
        method_name = payload.get("method")
        kwargs = payload.get("kwargs") or {}
        task_monitor_handoff_seq = self._task_monitor_handoff_seq(
            service_name,
            method_name,
        )

        factory = self.service_registry.get(service_name)
        if factory is None:
            return self._error(
                "UNKNOWN_SERVICE",
                f"지원하지 않는 서비스입니다: {service_name}",
            )

        service = self.async_service_builder(service_name, factory)
        async_method = getattr(service, f"async_{method_name}", None)
        method = async_method or getattr(service, method_name, None)
        if method is None:
            return self._error(
                "UNKNOWN_METHOD",
                f"지원하지 않는 메서드입니다: {service_name}.{method_name}",
            )

        try:
            if inspect.iscoroutinefunction(method):
                result = await method(**kwargs)
            else:
                result = await asyncio.to_thread(method, **kwargs)
        except Exception as exc:
            return self._error("RPC_ERROR", str(exc))

        await self._publish_task_update_if_needed(
            result,
            service_name=service_name,
            method_name=method_name,
        )

        result = self._attach_task_monitor_handoff_seq(result, task_monitor_handoff_seq)
        return RpcDispatchResult(ok=True, payload=result)

    async def _publish_task_update_if_needed(self, result, *, service_name, method_name):
        if self.task_update_publisher is None:
            return

        if service_name == "task_request" and method_name in {
            "cancel_delivery_task",
            "cancel_task",
        }:
            source = (
                "DELIVERY_CANCEL"
                if method_name == "cancel_delivery_task"
                else "TASK_CANCEL"
            )
            await self.task_update_publisher(
                result,
                source=source,
            )
            return

        if service_name == "visit_guide" and method_name in {
            "begin_guide_session",
            "send_guide_command",
            "finish_guide_session",
            "start_guide_driving",
        }:
            await self.task_update_publisher(
                self.extract_task_update_response(result),
                source="GUIDE_COMMAND",
                task_type="GUIDE",
            )

    def _task_monitor_handoff_seq(self, service_name, method_name):
        if (
            service_name == "task_monitor"
            and method_name == "get_task_monitor_snapshot"
            and self.task_monitor_watermark_provider is not None
        ):
            return self.task_monitor_watermark_provider()
        return None

    @staticmethod
    def _attach_task_monitor_handoff_seq(result, handoff_seq):
        if handoff_seq is None or not isinstance(result, dict):
            return result
        return {
            **result,
            "last_event_seq": handoff_seq,
        }

    @staticmethod
    def extract_task_update_response(result):
        if isinstance(result, dict):
            return result
        if isinstance(result, (list, tuple)) and len(result) >= 3:
            payload = result[2]
            if isinstance(payload, dict):
                return payload
        return {}

    @staticmethod
    def _default_service_builder(_service_name, factory):
        return factory()

    @staticmethod
    def _error(error_code, error_message):
        return RpcDispatchResult(
            ok=False,
            error_code=error_code,
            error_message=error_message,
        )


__all__ = ["ControlRpcDispatcher", "RpcDispatchResult"]
