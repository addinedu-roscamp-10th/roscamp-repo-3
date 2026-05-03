import asyncio

from server.ropi_main_service.application.visit_guide import VisitGuideService


class FakeGuideTaskRepository:
    def __init__(self):
        self.created = None

    def create_guide_task(self, **kwargs):
        self.created = kwargs
        return {
            "result_code": "ACCEPTED",
            "task_id": 3001,
            "task_status": "WAITING_DISPATCH",
            "phase": "WAIT_GUIDE_START_CONFIRM",
            "assigned_robot_id": "pinky1",
            "resident_name": "김*수",
            "room_no": "301",
            "destination_id": "delivery_room_301",
        }

    async def async_create_guide_task(self, **kwargs):
        self.created = kwargs
        return self.create_guide_task(**kwargs)


def test_visit_guide_service_create_guide_task_validates_required_fields():
    service = VisitGuideService(guide_task_repository=FakeGuideTaskRepository())

    response = service.create_guide_task(
        request_id="",
        visitor_id=1,
        idempotency_key="idem_guide_001",
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "REQUEST_ID_INVALID"


def test_visit_guide_service_create_guide_task_delegates_to_repository():
    repository = FakeGuideTaskRepository()
    service = VisitGuideService(guide_task_repository=repository)

    response = service.create_guide_task(
        request_id="req_guide_001",
        visitor_id="1",
        idempotency_key="idem_guide_001",
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 3001
    assert repository.created == {
        "request_id": "req_guide_001",
        "visitor_id": 1,
        "priority": "NORMAL",
        "idempotency_key": "idem_guide_001",
    }


def test_visit_guide_service_async_create_guide_task_uses_async_repository():
    repository = FakeGuideTaskRepository()
    service = VisitGuideService(guide_task_repository=repository)

    response = asyncio.run(
        service.async_create_guide_task(
            request_id="req_guide_001",
            visitor_id="1",
            idempotency_key="idem_guide_001",
        )
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["task_id"] == 3001
    assert repository.created["visitor_id"] == 1
