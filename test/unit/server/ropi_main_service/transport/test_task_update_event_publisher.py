import asyncio

from server.ropi_main_service.transport.task_update_event_publisher import (
    TaskUpdateEventPublisher,
)


def test_task_update_event_publisher_publishes_delivery_task_updated_payload():
    published = []

    async def publish_event(event_type, payload):
        published.append((event_type, payload))

    publisher = TaskUpdateEventPublisher(publish_event=publish_event)

    asyncio.run(
        publisher.publish_from_response(
            {
                "result_code": "ACCEPTED",
                "result_message": "작업이 접수되었습니다.",
                "task_id": 101,
                "task_status": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky2",
            },
            source="DELIVERY_CREATE",
        )
    )

    assert published == [
        (
            "TASK_UPDATED",
            {
                "source": "DELIVERY_CREATE",
                "task_id": 101,
                "task_type": "DELIVERY",
                "task_status": "WAITING_DISPATCH",
                "phase": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky2",
                "latest_reason_code": None,
                "result_code": "ACCEPTED",
                "result_message": "작업이 접수되었습니다.",
                "cancel_requested": None,
                "cancellable": None,
            },
        )
    ]


def test_task_update_event_publisher_builds_guide_detail_payload():
    published = []

    async def publish_event(event_type, payload):
        published.append((event_type, payload))

    publisher = TaskUpdateEventPublisher(publish_event=publish_event)

    asyncio.run(
        publisher.publish_from_response(
            {
                "result_code": "ACCEPTED",
                "result_message": "안내 요청이 접수되었습니다.",
                "task_id": 3001,
                "task_type": "GUIDE",
                "task_status": "WAITING_DISPATCH",
                "phase": "WAIT_GUIDE_START_CONFIRM",
                "assigned_robot_id": "pinky1",
                "visitor_id": 1,
                "visitor_name": "김민수",
                "relation_name": "아들",
                "member_id": 1,
                "resident_name": "김*수",
                "room_no": "301",
                "destination_id": "delivery_room_301",
                "destination_map_id": "map_test11_0423",
                "destination_zone_id": "room_301",
                "destination_zone_name": "301호",
                "destination_purpose": "DESTINATION",
            },
            source="GUIDE_CREATE",
            task_type="GUIDE",
        )
    )

    payload = published[0][1]
    assert published[0][0] == "TASK_UPDATED"
    assert payload["task_type"] == "GUIDE"
    assert payload["cancellable"] is False
    assert payload["guide_detail"] == {
        "guide_phase": "WAIT_GUIDE_START_CONFIRM",
        "target_track_id": None,
        "visitor_id": 1,
        "visitor_name": "김민수",
        "relation_name": "아들",
        "member_id": 1,
        "resident_name": "김*수",
        "room_no": "301",
        "destination_id": "delivery_room_301",
        "destination_map_id": "map_test11_0423",
        "destination_zone_id": "room_301",
        "destination_zone_name": "301호",
        "destination_purpose": "DESTINATION",
    }


def test_task_update_event_publisher_skips_invalid_response():
    published = []

    async def publish_event(event_type, payload):
        published.append((event_type, payload))

    publisher = TaskUpdateEventPublisher(publish_event=publish_event)

    asyncio.run(publisher.publish_from_response(None, source="DELIVERY_CREATE"))
    asyncio.run(publisher.publish_from_response({}, source="DELIVERY_CREATE"))

    assert published == []
