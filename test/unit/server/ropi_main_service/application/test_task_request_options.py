import asyncio

from server.ropi_main_service.application.task_request import DeliveryRequestService


class FakeTaskRequestOptionRepository:
    def __init__(self):
        self.patrol_create_payload = None

    def get_delivery_destinations(self):
        return [
            {
                "destination_id": "delivery_room_301",
                "destination_name": "301호",
                "zone_id": "room_301",
                "map_id": "map_test11_0423",
            }
        ]

    async def async_get_delivery_destinations(self):
        return self.get_delivery_destinations()

    def get_patrol_areas(self):
        return [
            {
                "patrol_area_id": "patrol_ward_night_01",
                "patrol_area_name": "야간 병동 순찰",
                "patrol_area_revision": 7,
                "map_id": "map_test11_0423",
                "waypoint_count": 3,
                "path_frame_id": "map",
            }
        ]

    async def async_get_patrol_areas(self):
        return self.get_patrol_areas()

    def create_patrol_task(self, **payload):
        self.patrol_create_payload = payload
        return {
            "result_code": "ACCEPTED",
            "task_id": 2001,
            "task_status": "WAITING_DISPATCH",
            "assigned_robot_id": "pinky3",
            "patrol_area_id": payload["patrol_area_id"],
            "patrol_area_name": "야간 병동 순찰",
            "patrol_area_revision": 7,
        }

    async def async_create_patrol_task(self, **payload):
        return self.create_patrol_task(**payload)


def test_task_request_service_exposes_db_backed_delivery_destinations():
    service = DeliveryRequestService(repository=FakeTaskRequestOptionRepository())

    destinations = service.get_delivery_destinations()

    assert destinations == [
        {
            "destination_id": "delivery_room_301",
            "destination_name": "301호",
            "display_name": "301호",
            "zone_id": "room_301",
            "map_id": "map_test11_0423",
        }
    ]


def test_task_request_service_exposes_db_backed_patrol_area_metadata():
    service = DeliveryRequestService(repository=FakeTaskRequestOptionRepository())

    patrol_areas = service.get_patrol_areas()

    assert patrol_areas == [
        {
            "patrol_area_id": "patrol_ward_night_01",
            "patrol_area_name": "야간 병동 순찰",
            "patrol_area_revision": 7,
            "waypoint_count": 3,
            "path_frame_id": "map",
            "active": True,
            "map_id": "map_test11_0423",
        }
    ]


def test_task_request_service_option_methods_have_async_variants():
    service = DeliveryRequestService(repository=FakeTaskRequestOptionRepository())

    async def scenario():
        return (
            await service.async_get_delivery_destinations(),
            await service.async_get_patrol_areas(),
        )

    destinations, patrol_areas = asyncio.run(scenario())

    assert destinations[0]["destination_id"] == "delivery_room_301"
    assert patrol_areas[0]["waypoint_count"] == 3


def test_task_request_service_creates_patrol_task_from_pat_001_payload():
    repository = FakeTaskRequestOptionRepository()
    service = DeliveryRequestService(repository=repository)

    response = service.create_patrol_task(
        request_id="req_patrol_001",
        caregiver_id=1,
        patrol_area_id="patrol_ward_night_01",
        priority="NORMAL",
        idempotency_key="idem_patrol_001",
    )

    assert response == {
        "result_code": "ACCEPTED",
        "task_id": 2001,
        "task_status": "WAITING_DISPATCH",
        "assigned_robot_id": "pinky3",
        "patrol_area_id": "patrol_ward_night_01",
        "patrol_area_name": "야간 병동 순찰",
        "patrol_area_revision": 7,
    }
    assert repository.patrol_create_payload == {
        "request_id": "req_patrol_001",
        "caregiver_id": 1,
        "patrol_area_id": "patrol_ward_night_01",
        "priority": "NORMAL",
        "idempotency_key": "idem_patrol_001",
    }


def test_task_request_service_rejects_invalid_patrol_create_payload():
    service = DeliveryRequestService(repository=FakeTaskRequestOptionRepository())

    response = service.create_patrol_task(
        request_id="req_patrol_001",
        caregiver_id=1,
        patrol_area_id="",
        priority="NORMAL",
        idempotency_key="idem_patrol_001",
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "PATROL_AREA_ID_INVALID"
