import asyncio

from server.ropi_main_service.application.guide_tracking_update import (
    GUIDE_TRACKING_UPDATE_COMMAND,
    GuideTrackingUpdatePublisherService,
)


class FakeCommandClient:
    def __init__(self):
        self.calls = []
        self.async_calls = []

    def send_command(self, command, payload, *, timeout):
        self.calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {"result_code": "ACCEPTED", "accepted": True}

    async def async_send_command(self, command, payload, *, timeout):
        self.async_calls.append(
            {
                "command": command,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return {"result_code": "ACCEPTED", "accepted": True}


def test_guide_tracking_update_publisher_sends_normalized_uds_command():
    command_client = FakeCommandClient()
    service = GuideTrackingUpdatePublisherService(
        command_client=command_client,
        timeout_sec=1.5,
    )

    response = service.publish(
        pinky_id="pinky1",
        task_id=3001,
        target_track_id="track_17",
        tracking_status="TRACKING",
        tracking_result_seq="881",
        frame_ts="2026-04-19T12:35:10Z",
        bbox_valid=True,
        bbox_xyxy=["120", "80", "300", "420"],
        image_width_px="640",
        image_height_px="480",
    )

    assert response == {"result_code": "ACCEPTED", "accepted": True}
    assert command_client.calls == [
        {
            "command": GUIDE_TRACKING_UPDATE_COMMAND,
            "payload": {
                "pinky_id": "pinky1",
                "task_id": "3001",
                "target_track_id": "track_17",
                "tracking_status": "TRACKING",
                "tracking_result_seq": 881,
                "frame_ts_sec": 1776602110,
                "frame_ts_nanosec": 0,
                "bbox_valid": True,
                "bbox_xyxy": [120, 80, 300, 420],
                "image_width_px": 640,
                "image_height_px": 480,
            },
            "timeout": 1.5,
        }
    ]


def test_guide_tracking_update_publisher_async_uses_async_command_client():
    command_client = FakeCommandClient()
    service = GuideTrackingUpdatePublisherService(command_client=command_client)

    async def scenario():
        return await service.async_publish(
            pinky_id="pinky1",
            task_id="3001",
            target_track_id="track_17",
            tracking_status="LOST",
            tracking_result_seq=882,
            frame_ts_sec=1776598511,
            frame_ts_nanosec=1000,
            bbox_valid=False,
            bbox_xyxy=[1, 2, 3, 4],
            image_width_px=640,
            image_height_px=480,
        )

    response = asyncio.run(scenario())

    assert response["result_code"] == "ACCEPTED"
    assert command_client.async_calls[0]["command"] == GUIDE_TRACKING_UPDATE_COMMAND
    assert command_client.async_calls[0]["payload"]["tracking_status"] == "LOST"
    assert command_client.async_calls[0]["payload"]["bbox_valid"] is False
    assert command_client.async_calls[0]["payload"]["bbox_xyxy"] == [0, 0, 0, 0]
