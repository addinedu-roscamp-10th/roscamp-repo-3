import asyncio

from server.ropi_main_service.application.task_request import DeliveryRequestService


class FakeTaskRequestOptionRepository:
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
            }
        ]

    async def async_get_patrol_areas(self):
        return self.get_patrol_areas()


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


def test_task_request_service_exposes_phase1_patrol_areas_with_fixed_robot():
    service = DeliveryRequestService(repository=FakeTaskRequestOptionRepository())

    patrol_areas = service.get_patrol_areas()

    assert patrol_areas == [
        {
            "patrol_area_id": "patrol_ward_night_01",
            "patrol_area_name": "야간 병동 순찰",
            "patrol_area_revision": 7,
            "assigned_robot_id": "pinky3",
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
    assert patrol_areas[0]["assigned_robot_id"] == "pinky3"
