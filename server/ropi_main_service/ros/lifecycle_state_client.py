import asyncio
import time


class RclpyLifecycleStateClient:
    def __init__(
        self,
        *,
        node,
        service_type_loader=None,
        client_factory=None,
    ):
        self.node = node
        self.service_type_loader = service_type_loader or self._load_default_service_type
        self.client_factory = client_factory or self._load_default_client_factory()
        self._clients = {}

    def get_state(self, *, node_name, timeout_sec=0.15):
        client = self._get_client(node_name)
        timeout_sec = self._normalize_timeout_sec(timeout_sec)
        if not client.wait_for_service(timeout_sec=timeout_sec):
            return None

        future = client.call_async(self.service_type_loader().Request())
        if not self._wait_for_future(future, timeout_sec=timeout_sec):
            return None
        return self._response_to_state(future.result())

    async def async_get_state(self, *, node_name, timeout_sec=0.15):
        client = self._get_client(node_name)
        timeout_sec = self._normalize_timeout_sec(timeout_sec)
        if not client.wait_for_service(timeout_sec=timeout_sec):
            return None

        future = client.call_async(self.service_type_loader().Request())
        if not await self._async_wait_for_future(future, timeout_sec=timeout_sec):
            return None
        return self._response_to_state(future.result())

    def _get_client(self, node_name):
        service_name = self._build_get_state_service_name(node_name)
        client = self._clients.get(service_name)
        if client is None:
            client = self.client_factory(
                self.node,
                self.service_type_loader(),
                service_name,
            )
            self._clients[service_name] = client
        return client

    @staticmethod
    def _build_get_state_service_name(node_name):
        normalized = str(node_name or "").strip().rstrip("/")
        return f"{normalized}/get_state"

    @staticmethod
    def _response_to_state(response):
        state = getattr(response, "current_state", None)
        if state is None:
            return None
        return {
            "id": getattr(state, "id", None),
            "label": getattr(state, "label", None),
        }

    @staticmethod
    def _wait_for_future(future, *, timeout_sec):
        deadline = time.monotonic() + timeout_sec
        while not future.done():
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        return True

    @staticmethod
    async def _async_wait_for_future(future, *, timeout_sec):
        deadline = time.monotonic() + timeout_sec
        while not future.done():
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        return True

    @staticmethod
    def _normalize_timeout_sec(timeout_sec):
        try:
            return max(0.0, float(timeout_sec))
        except (TypeError, ValueError):
            return 0.15

    @staticmethod
    def _load_default_service_type():
        from lifecycle_msgs.srv import GetState

        return GetState

    @staticmethod
    def _load_default_client_factory():
        return lambda node, service_type, service_name: node.create_client(
            service_type,
            service_name,
        )


__all__ = ["RclpyLifecycleStateClient"]
