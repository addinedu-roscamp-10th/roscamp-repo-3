import asyncio
from datetime import datetime, timezone

from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
    TCPFrame,
    encode_frame,
)


class TaskEventStreamHub:
    def __init__(self, *, max_buffer_size=1000):
        self.max_buffer_size = max(1, int(max_buffer_size))
        self._events = []
        self._next_event_seq = 1
        self._subscribers = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, *, consumer_id, last_seq, writer, replay=True):
        normalized_consumer_id = str(consumer_id or "").strip()
        if not normalized_consumer_id:
            return {
                "result_code": "INVALID_REQUEST",
                "result_message": "consumer_id가 필요합니다.",
                "accepted_consumer_id": None,
            }

        async with self._lock:
            self._subscribers[normalized_consumer_id] = writer
            replay_events = self._events_after(last_seq)

        if replay and replay_events:
            await self._write_push_frame(writer, replay_events)

        return {
            "result_code": "ACCEPTED",
            "result_message": None,
            "accepted_consumer_id": normalized_consumer_id,
        }

    async def replay(self, *, consumer_id, last_seq):
        normalized_consumer_id = str(consumer_id or "").strip()
        if not normalized_consumer_id:
            return

        async with self._lock:
            writer = self._subscribers.get(normalized_consumer_id)
            replay_events = self._events_after(last_seq)

        if writer is not None and replay_events:
            await self._write_push_frame(writer, replay_events)

    async def unsubscribe(self, consumer_id=None, *, writer=None):
        normalized_consumer_id = str(consumer_id or "").strip()

        async with self._lock:
            if normalized_consumer_id:
                self._subscribers.pop(normalized_consumer_id, None)
                return

            if writer is None:
                return

            stale_consumers = [
                subscribed_consumer_id
                for (
                    subscribed_consumer_id,
                    subscribed_writer,
                ) in self._subscribers.items()
                if subscribed_writer is writer
            ]
            for stale_consumer_id in stale_consumers:
                self._subscribers.pop(stale_consumer_id, None)

    async def publish(self, event_type, payload, *, occurred_at=None):
        async with self._lock:
            event = self._build_event(
                event_type=event_type,
                payload=payload,
                occurred_at=occurred_at,
            )
            self._events.append(event)
            if len(self._events) > self.max_buffer_size:
                self._events = self._events[-self.max_buffer_size:]
            subscribers = list(self._subscribers.items())

        stale_consumers = []
        for consumer_id, writer in subscribers:
            try:
                await self._write_push_frame(writer, [event])
            except Exception:
                stale_consumers.append(consumer_id)

        if stale_consumers:
            async with self._lock:
                for consumer_id in stale_consumers:
                    self._subscribers.pop(consumer_id, None)

        return event

    def _build_event(self, *, event_type, payload, occurred_at=None):
        event_seq = self._next_event_seq
        self._next_event_seq += 1
        return {
            "event_seq": event_seq,
            "event_type": str(event_type or "").strip(),
            "occurred_at": occurred_at or datetime.now(timezone.utc).isoformat(),
            "payload": payload or {},
        }

    def _events_after(self, last_seq):
        try:
            normalized_last_seq = int(last_seq or 0)
        except (TypeError, ValueError):
            normalized_last_seq = 0
        return [
            event
            for event in self._events
            if int(event.get("event_seq") or 0) > normalized_last_seq
        ]

    async def _write_push_frame(self, writer, events):
        batch_end_seq = max(int(event["event_seq"]) for event in events)
        frame = TCPFrame(
            message_code=MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
            sequence_no=batch_end_seq,
            payload={
                "batch_end_seq": batch_end_seq,
                "events": events,
            },
            is_push=True,
        )
        writer.write(encode_frame(frame))
        await writer.drain()


__all__ = ["TaskEventStreamHub"]
