import asyncio

from server.ropi_main_service.transport.task_event_subscription_handler import (
    TaskEventSubscriptionHandler,
)


class FakeTaskEventStreamHub:
    def __init__(self, ack=None):
        self.ack = ack or {
            "result_code": "ACCEPTED",
            "accepted_consumer_id": "monitor-1",
        }
        self.subscribed = []
        self.replayed = []

    async def subscribe(self, **kwargs):
        self.subscribed.append(kwargs)
        return self.ack

    async def replay(self, **kwargs):
        self.replayed.append(kwargs)


def test_task_event_subscription_handler_accepts_subscribe_and_preserves_ack():
    hub = FakeTaskEventStreamHub()
    handler = TaskEventSubscriptionHandler(stream_hub=hub)
    writer = object()

    result = asyncio.run(
        handler.subscribe(
            {
                "consumer_id": "monitor-1",
                "last_seq": 42,
            },
            writer=writer,
        )
    )

    assert result.accepted is True
    assert result.payload == {
        "result_code": "ACCEPTED",
        "accepted_consumer_id": "monitor-1",
    }
    assert result.error_code == ""
    assert hub.subscribed == [
        {
            "consumer_id": "monitor-1",
            "last_seq": 42,
            "writer": writer,
            "replay": False,
        }
    ]


def test_task_event_subscription_handler_reports_rejected_subscribe():
    hub = FakeTaskEventStreamHub(
        ack={
            "result_code": "INVALID_REQUEST",
            "result_message": "consumer_id가 필요합니다.",
        }
    )
    handler = TaskEventSubscriptionHandler(stream_hub=hub)

    result = asyncio.run(handler.subscribe({}, writer=object()))

    assert result.accepted is False
    assert result.error_code == "TASK_EVENT_SUBSCRIBE_ERROR"
    assert result.error_message == "consumer_id가 필요합니다."


def test_task_event_subscription_handler_replays_only_after_successful_subscribe():
    hub = FakeTaskEventStreamHub()
    handler = TaskEventSubscriptionHandler(stream_hub=hub)

    asyncio.run(
        handler.replay_after_subscribe(
            {
                "consumer_id": "monitor-1",
                "last_seq": 42,
            },
            subscribe_accepted=True,
        )
    )
    asyncio.run(
        handler.replay_after_subscribe(
            {
                "consumer_id": "monitor-1",
                "last_seq": 43,
            },
            subscribe_accepted=False,
        )
    )

    assert hub.replayed == [
        {
            "consumer_id": "monitor-1",
            "last_seq": 42,
        }
    ]
