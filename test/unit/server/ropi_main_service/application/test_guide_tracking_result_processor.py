import asyncio

from server.ropi_main_service.application.guide_tracking_result import (
    GuideTrackingResultProcessor,
)


class FakeGuideTrackingRepository:
    def __init__(self, active_task=None):
        self.active_task = active_task
        self.queries = []

    async def async_get_active_guide_task_for_robot(self, robot_id):
        self.queries.append(robot_id)
        return self.active_task


class FakeGuideTrackingUpdatePublisher:
    def __init__(self):
        self.updates = []

    async def async_publish(self, **payload):
        self.updates.append(payload)
        return {"result_code": "ACCEPTED", "accepted": True}


def test_processor_publishes_tracking_bbox_for_active_guide_target():
    repository = FakeGuideTrackingRepository(
        active_task={
            "task_id": 3001,
            "assigned_robot_id": "pinky1",
            "target_track_id": "track_17",
            "task_status": "RUNNING",
            "phase": "GUIDANCE_RUNNING",
        }
    )
    publisher = FakeGuideTrackingUpdatePublisher()
    processor = GuideTrackingResultProcessor(
        repository=repository,
        update_publisher=publisher,
    )

    async def scenario():
        return await processor.async_process_batch(
            {
                "results": [
                    {
                        "result_seq": 881,
                        "pinky_id": "pinky1",
                        "frame_ts": "2026-04-19T12:35:10Z",
                        "tracking_status": "TRACKING",
                        "active_track_id": "track_17",
                        "confidence": 0.91,
                        "image_width_px": 640,
                        "image_height_px": 480,
                        "candidate_tracks": [
                            {
                                "track_id": "track_17",
                                "bbox_xyxy": [120, 80, 300, 420],
                                "score": 0.91,
                            }
                        ],
                    }
                ]
            }
        )

    summary = asyncio.run(scenario())

    assert summary == {
        "processed_count": 1,
        "published_count": 1,
        "ignored_count": 0,
        "failed_count": 0,
    }
    assert repository.queries == ["pinky1"]
    assert publisher.updates == [
        {
            "pinky_id": "pinky1",
            "task_id": 3001,
            "target_track_id": "track_17",
            "tracking_status": "TRACKING",
            "tracking_result_seq": 881,
            "frame_ts": "2026-04-19T12:35:10Z",
            "bbox_valid": True,
            "bbox_xyxy": [120, 80, 300, 420],
            "image_width_px": 640,
            "image_height_px": 480,
        }
    ]


def test_processor_publishes_lost_update_without_bbox():
    repository = FakeGuideTrackingRepository(
        active_task={
            "task_id": 3001,
            "assigned_robot_id": "pinky1",
            "target_track_id": "track_17",
            "task_status": "RUNNING",
            "phase": "GUIDANCE_RUNNING",
        }
    )
    publisher = FakeGuideTrackingUpdatePublisher()
    processor = GuideTrackingResultProcessor(
        repository=repository,
        update_publisher=publisher,
    )

    async def scenario():
        return await processor.async_process_batch(
            {
                "results": [
                    {
                        "result_seq": 882,
                        "pinky_id": "pinky1",
                        "frame_ts": "2026-04-19T12:35:11Z",
                        "tracking_status": "LOST",
                        "active_track_id": "track_17",
                        "confidence": 0.0,
                        "image_width_px": 640,
                        "image_height_px": 480,
                        "candidate_tracks": [],
                    }
                ]
            }
        )

    summary = asyncio.run(scenario())

    assert summary["published_count"] == 1
    assert publisher.updates[0]["tracking_status"] == "LOST"
    assert publisher.updates[0]["bbox_valid"] is False
    assert publisher.updates[0]["bbox_xyxy"] == [0, 0, 0, 0]


def test_processor_ignores_result_without_matching_active_guide_task():
    repository = FakeGuideTrackingRepository(active_task=None)
    publisher = FakeGuideTrackingUpdatePublisher()
    processor = GuideTrackingResultProcessor(
        repository=repository,
        update_publisher=publisher,
    )

    async def scenario():
        return await processor.async_process_batch(
            {
                "results": [
                    {
                        "result_seq": 881,
                        "pinky_id": "pinky1",
                        "frame_ts": "2026-04-19T12:35:10Z",
                        "tracking_status": "TRACKING",
                        "active_track_id": "track_17",
                        "confidence": 0.91,
                        "image_width_px": 640,
                        "image_height_px": 480,
                        "candidate_tracks": [
                            {
                                "track_id": "track_17",
                                "bbox_xyxy": [120, 80, 300, 420],
                                "score": 0.91,
                            }
                        ],
                    }
                ]
            }
        )

    summary = asyncio.run(scenario())

    assert summary["published_count"] == 0
    assert summary["ignored_count"] == 1
    assert publisher.updates == []


def test_processor_ignores_tracking_result_for_other_track_id():
    repository = FakeGuideTrackingRepository(
        active_task={
            "task_id": 3001,
            "assigned_robot_id": "pinky1",
            "target_track_id": "track_17",
            "task_status": "RUNNING",
            "phase": "GUIDANCE_RUNNING",
        }
    )
    publisher = FakeGuideTrackingUpdatePublisher()
    processor = GuideTrackingResultProcessor(
        repository=repository,
        update_publisher=publisher,
    )

    async def scenario():
        return await processor.async_process_batch(
            {
                "results": [
                    {
                        "result_seq": 881,
                        "pinky_id": "pinky1",
                        "frame_ts": "2026-04-19T12:35:10Z",
                        "tracking_status": "TRACKING",
                        "active_track_id": "track_99",
                        "confidence": 0.91,
                        "image_width_px": 640,
                        "image_height_px": 480,
                        "candidate_tracks": [
                            {
                                "track_id": "track_99",
                                "bbox_xyxy": [120, 80, 300, 420],
                                "score": 0.91,
                            }
                        ],
                    }
                ]
            }
        )

    summary = asyncio.run(scenario())

    assert summary["published_count"] == 0
    assert summary["ignored_count"] == 1
    assert publisher.updates == []
