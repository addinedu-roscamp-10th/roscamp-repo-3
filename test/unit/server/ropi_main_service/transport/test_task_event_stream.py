import asyncio

from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_TASK_EVENT_SUBSCRIBE,
    decode_frame_bytes,
)


class FakeStreamWriter:
    def __init__(self):
        self.frames = []
        self.drain_count = 0

    def write(self, data):
        self.frames.append(decode_frame_bytes(data))

    async def drain(self):
        self.drain_count += 1


def test_task_event_stream_hub_publishes_push_frames_to_subscribers():
    from server.ropi_main_service.transport.task_event_stream import TaskEventStreamHub

    async def scenario():
        writer = FakeStreamWriter()
        hub = TaskEventStreamHub()

        ack = await hub.subscribe(
            consumer_id="ui-admin",
            last_seq=0,
            writer=writer,
        )
        await hub.publish(
            "TASK_UPDATED",
            {
                "task_id": 1001,
                "task_status": "RUNNING",
            },
        )
        return ack, writer

    ack, writer = asyncio.run(scenario())

    assert ack == {
        "result_code": "ACCEPTED",
        "result_message": None,
        "accepted_consumer_id": "ui-admin",
    }
    assert len(writer.frames) == 1
    push = writer.frames[0]
    assert push.message_code == MESSAGE_CODE_TASK_EVENT_SUBSCRIBE
    assert push.is_push is True
    assert push.payload["batch_end_seq"] == 1
    assert push.payload["events"][0]["event_seq"] == 1
    assert push.payload["events"][0]["event_type"] == "TASK_UPDATED"
    assert push.payload["events"][0]["payload"]["task_id"] == 1001


def test_task_event_stream_hub_replays_events_after_last_seq():
    from server.ropi_main_service.transport.task_event_stream import TaskEventStreamHub

    async def scenario():
        writer = FakeStreamWriter()
        hub = TaskEventStreamHub()

        await hub.publish("TASK_UPDATED", {"task_id": 1001})
        await hub.publish("ACTION_FEEDBACK_UPDATED", {"task_id": 1001})
        ack = await hub.subscribe(
            consumer_id="ui-admin",
            last_seq=1,
            writer=writer,
        )
        return ack, writer

    ack, writer = asyncio.run(scenario())

    assert ack["result_code"] == "ACCEPTED"
    assert len(writer.frames) == 1
    assert writer.frames[0].payload["batch_end_seq"] == 2
    assert [event["event_seq"] for event in writer.frames[0].payload["events"]] == [2]
