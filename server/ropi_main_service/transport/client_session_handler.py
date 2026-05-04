from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
    TCPFrame,
    TCPFrameError,
    read_frame_from_stream,
)


class ControlClientSessionHandler:
    def __init__(
        self,
        *,
        stream_hub,
        task_event_subscription_handler,
        build_response_frame,
        encode_response,
        success_response,
        error_response,
        read_frame=read_frame_from_stream,
    ):
        self.stream_hub = stream_hub
        self.task_event_subscription_handler = task_event_subscription_handler
        self.build_response_frame = build_response_frame
        self.encode_response = encode_response
        self.success_response = success_response
        self.error_response = error_response
        self.read_frame = read_frame

    async def handle_client(self, reader, writer):
        try:
            while not reader.at_eof():
                try:
                    request_frame = await self.read_frame(reader)
                except TCPFrameError:
                    break

                if request_frame.message_code == MESSAGE_CODE_TASK_EVENT_SUBSCRIBE:
                    response_frame = await self.handle_task_event_subscribe(
                        request_frame,
                        writer,
                    )
                    writer.write(self.encode_response(response_frame))
                    await writer.drain()
                    await self.replay_task_events_after_subscribe(
                        request_frame,
                        response_frame,
                    )
                    continue

                response_frame = await self.build_response_frame(request_frame)
                writer.write(self.encode_response(response_frame))
                await writer.drain()
        finally:
            await self.stream_hub.unsubscribe(writer=writer)
            writer.close()
            await writer.wait_closed()

    async def handle_task_event_subscribe(
        self,
        frame: TCPFrame,
        writer,
    ) -> TCPFrame:
        result = await self.task_event_subscription_handler.subscribe(
            frame.payload or {},
            writer=writer,
        )
        if not result.accepted:
            return self.error_response(
                frame,
                result.error_code,
                result.error_message,
            )
        return self.success_response(frame, result.payload)

    async def replay_task_events_after_subscribe(
        self,
        frame: TCPFrame,
        response_frame: TCPFrame,
    ):
        if response_frame.is_error:
            return

        await self.task_event_subscription_handler.replay_after_subscribe(
            frame.payload or {},
            subscribe_accepted=True,
        )


__all__ = ["ControlClientSessionHandler"]
