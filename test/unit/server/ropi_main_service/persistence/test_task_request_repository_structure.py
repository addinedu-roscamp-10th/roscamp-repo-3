from server.ropi_main_service.persistence.repositories import (
    DeliveryRequestEventRepository,
)
from server.ropi_main_service.persistence.repositories.task_request_repository import (
    TaskRequestRepository,
)


class FakeLookupRepository:
    def __init__(self):
        self.calls = []

    def get_all_products(self):
        self.calls.append("get_all_products")
        return [{"item_id": 1}]

    async def async_get_all_products(self):
        self.calls.append("async_get_all_products")
        return [{"item_id": 1}]

    def get_enabled_goal_poses(self):
        self.calls.append("get_enabled_goal_poses")
        return [{"goal_pose_id": "delivery_room_301"}]

    async def async_get_enabled_goal_poses(self):
        self.calls.append("async_get_enabled_goal_poses")
        return [{"goal_pose_id": "delivery_room_301"}]

    def get_delivery_destinations(self):
        self.calls.append("get_delivery_destinations")
        return [{"destination_id": "delivery_room_301"}]

    async def async_get_delivery_destinations(self):
        self.calls.append("async_get_delivery_destinations")
        return [{"destination_id": "delivery_room_301"}]

    def get_patrol_areas(self):
        self.calls.append("get_patrol_areas")
        return [{"patrol_area_id": "patrol_ward_night_01"}]

    async def async_get_patrol_areas(self):
        self.calls.append("async_get_patrol_areas")
        return [{"patrol_area_id": "patrol_ward_night_01"}]

    def get_product_by_name(self, item_name, conn=None):
        self.calls.append(("get_product_by_name", item_name, conn))
        return {"item_name": item_name}


class FakeDeliveryRequestEventRepository:
    def __init__(self):
        self.created = None

    def create_delivery_request(self, **payload):
        self.created = payload
        return True, "물품 요청이 접수되었습니다."


def test_delivery_request_event_repository_is_public_member_event_writer_name():
    assert DeliveryRequestEventRepository.__name__ == "DeliveryRequestEventRepository"


def test_task_request_repository_delegates_option_reads_to_lookup_repository():
    lookup_repository = FakeLookupRepository()
    repository = TaskRequestRepository(
        lookup_repository=lookup_repository,
        delivery_request_event_repository=FakeDeliveryRequestEventRepository(),
    )

    assert repository.get_all_products() == [{"item_id": 1}]
    assert repository.get_enabled_goal_poses() == [
        {"goal_pose_id": "delivery_room_301"}
    ]
    assert repository.get_delivery_destinations() == [
        {"destination_id": "delivery_room_301"}
    ]
    assert repository.get_patrol_areas() == [
        {"patrol_area_id": "patrol_ward_night_01"}
    ]

    assert lookup_repository.calls == [
        "get_all_products",
        "get_enabled_goal_poses",
        "get_delivery_destinations",
        "get_patrol_areas",
    ]


def test_task_request_repository_delegates_delivery_request_event_creation():
    event_repository = FakeDeliveryRequestEventRepository()
    repository = TaskRequestRepository(
        lookup_repository=FakeLookupRepository(),
        delivery_request_event_repository=event_repository,
    )

    assert repository.create_delivery_request(
        item_name="물티슈",
        quantity=2,
        destination="301호",
        priority="긴급",
        detail="요청",
        member_id="7",
    ) == (True, "물품 요청이 접수되었습니다.")

    assert event_repository.created == {
        "item_name": "물티슈",
        "quantity": 2,
        "destination": "301호",
        "priority": "긴급",
        "detail": "요청",
        "member_id": "7",
    }
