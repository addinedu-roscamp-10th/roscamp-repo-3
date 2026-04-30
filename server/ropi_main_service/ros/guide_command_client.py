import asyncio

from server.ropi_main_service.ros.action_client_base import BaseRclpyActionClient


class RclpyGuideCommandClient:
    def __init__(
        self,
        *,
        node,
        service_type_loader=None,
        service_client_factory=None,
        server_wait_timeout_sec=5.0,
        response_wait_timeout_sec=5.0,
    ):
        self.node = node
        self.service_type_loader = service_type_loader or self._load_default_service_type
        self.service_client_factory = service_client_factory or self._load_default_service_client_factory
        self.server_wait_timeout_sec = float(server_wait_timeout_sec)
        self.response_wait_timeout_sec = float(response_wait_timeout_sec)

    def call(self, *, service_name, request):
        service_type = self.service_type_loader()
        service_client = self.service_client_factory(self.node, service_type, service_name)
        if not service_client.wait_for_service(timeout_sec=self.server_wait_timeout_sec):
            raise RuntimeError(f"{service_name} service is not available.")

        request_msg = self._build_request_message(service_type, request)
        response_msg = BaseRclpyActionClient._wait_for_future(
            service_client.call_async(request_msg),
            timeout_sec=self.response_wait_timeout_sec,
            error_message=f"{service_name} service response timed out.",
        )
        return BaseRclpyActionClient._message_to_dict(response_msg)

    async def async_call(self, *, service_name, request):
        service_type = self.service_type_loader()
        service_client = self.service_client_factory(self.node, service_type, service_name)
        if not await self._async_wait_for_service(
            service_client,
            timeout_sec=self.server_wait_timeout_sec,
        ):
            raise RuntimeError(f"{service_name} service is not available.")

        request_msg = self._build_request_message(service_type, request)
        response_msg = await BaseRclpyActionClient._wait_for_future_async(
            service_client.call_async(request_msg),
            timeout_sec=self.response_wait_timeout_sec,
            error_message=f"{service_name} service response timed out.",
        )
        return BaseRclpyActionClient._message_to_dict(response_msg)

    @staticmethod
    def _build_request_message(service_type, request):
        request_msg = service_type.Request()
        BaseRclpyActionClient._assign_attributes(request_msg, request or {})
        return request_msg

    @staticmethod
    async def _async_wait_for_service(service_client, *, timeout_sec):
        service_is_ready = getattr(service_client, "service_is_ready", None)
        if service_is_ready is None:
            return await asyncio.to_thread(
                service_client.wait_for_service,
                timeout_sec=timeout_sec,
            )

        if timeout_sec is not None and float(timeout_sec) <= 0:
            return bool(service_is_ready())

        loop = asyncio.get_running_loop()
        deadline = None if timeout_sec is None else loop.time() + float(timeout_sec)

        while True:
            if service_is_ready():
                return True

            if deadline is not None:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return False
                await asyncio.sleep(min(0.05, remaining))
                continue

            await asyncio.sleep(0.05)

    @staticmethod
    def _load_default_service_client_factory(node, service_type, service_name):
        return node.create_client(service_type, service_name)

    @staticmethod
    def _load_default_service_type():
        try:
            from ropi_interface.srv import GuideCommand
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "ropi_interface.srv.GuideCommand 를 불러올 수 없습니다. "
                "ROS workspace를 build/source 했는지 확인하세요."
            ) from exc

        return GuideCommand


__all__ = ["RclpyGuideCommandClient"]
