from dataclasses import dataclass


@dataclass(frozen=True)
class TaskEventSubscribeResult:
    accepted: bool
    payload: dict
    error_code: str = ""
    error_message: str = ""


class TaskEventSubscriptionHandler:
    def __init__(self, *, stream_hub):
        self.stream_hub = stream_hub

    async def subscribe(self, payload, *, writer):
        payload = payload or {}
        ack = await self.stream_hub.subscribe(
            consumer_id=payload.get("consumer_id"),
            last_seq=payload.get("last_seq", 0),
            writer=writer,
            replay=False,
        )
        if ack.get("result_code") != "ACCEPTED":
            return TaskEventSubscribeResult(
                accepted=False,
                payload=ack,
                error_code="TASK_EVENT_SUBSCRIBE_ERROR",
                error_message=(
                    ack.get("result_message") or "task event 구독 요청이 거부되었습니다."
                ),
            )
        return TaskEventSubscribeResult(accepted=True, payload=ack)

    async def replay_after_subscribe(self, payload, *, subscribe_accepted):
        if not subscribe_accepted:
            return

        payload = payload or {}
        await self.stream_hub.replay(
            consumer_id=payload.get("consumer_id"),
            last_seq=payload.get("last_seq", 0),
        )


__all__ = ["TaskEventSubscribeResult", "TaskEventSubscriptionHandler"]
