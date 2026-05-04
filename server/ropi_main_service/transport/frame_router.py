from dataclasses import dataclass


DEFAULT_STREAM_REQUIRED_MESSAGE = (
    "task event subscribe는 persistent TCP stream에서만 처리됩니다."
)


@dataclass(frozen=True)
class FrameRouteResult:
    handled: bool
    response: object = None
    error_code: str = ""
    error_message: str = ""


class ControlFrameRouter:
    def __init__(
        self,
        *,
        sync_routes=None,
        async_routes=None,
        sync_stream_required_codes=None,
        async_stream_required_codes=None,
        stream_required_message=DEFAULT_STREAM_REQUIRED_MESSAGE,
    ):
        self.sync_routes = sync_routes or {}
        self.async_routes = async_routes or {}
        self.sync_stream_required_codes = set(sync_stream_required_codes or ())
        self.async_stream_required_codes = set(async_stream_required_codes or ())
        self.stream_required_message = stream_required_message

    def dispatch(self, frame, *, loop=None):
        if frame.message_code in self.sync_stream_required_codes:
            return self._stream_required()

        handler = self.sync_routes.get(frame.message_code)
        if handler is None:
            return self._unknown_message_code(frame.message_code)

        response = handler(frame, frame.payload or {}, loop=loop)
        return FrameRouteResult(handled=True, response=response)

    async def async_dispatch(self, frame):
        if frame.message_code in self.async_stream_required_codes:
            return self._stream_required()

        handler = self.async_routes.get(frame.message_code)
        if handler is None:
            return self._unknown_message_code(frame.message_code)

        response = await handler(frame, frame.payload or {})
        return FrameRouteResult(handled=True, response=response)

    def _stream_required(self):
        return FrameRouteResult(
            handled=False,
            error_code="STREAM_REQUIRED",
            error_message=self.stream_required_message,
        )

    @staticmethod
    def _unknown_message_code(message_code):
        return FrameRouteResult(
            handled=False,
            error_code="UNKNOWN_MESSAGE_CODE",
            error_message=f"지원하지 않는 message_code입니다: 0x{message_code:04x}",
        )


__all__ = [
    "ControlFrameRouter",
    "DEFAULT_STREAM_REQUIRED_MESSAGE",
    "FrameRouteResult",
]
