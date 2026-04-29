import asyncio

from server.ropi_main_service.application.patrol_task_create import (
    PatrolTaskCreateService,
)


class FakePatrolTaskRepository:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create_patrol_task(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.response)

    async def async_create_patrol_task(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.response)


class FakeWorkflowStarter:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


def build_patrol_payload():
    return {
        "request_id": "req_patrol_001",
        "caregiver_id": "1",
        "patrol_area_id": "patrol_ward_night_01",
        "priority": "NORMAL",
        "idempotency_key": "idem_patrol_001",
    }


def test_create_patrol_task_validates_and_starts_workflow_after_acceptance():
    repository = FakePatrolTaskRepository(
        response={
            "result_code": "ACCEPTED",
            "task_id": 2001,
            "task_status": "WAITING_DISPATCH",
            "assigned_robot_id": "pinky3",
        }
    )
    workflow_starter = FakeWorkflowStarter()
    service = PatrolTaskCreateService(
        repository=repository,
        patrol_workflow_starter=workflow_starter,
    )

    response = service.create_patrol_task(**build_patrol_payload())

    assert response["result_code"] == "ACCEPTED"
    assert repository.calls == [build_patrol_payload()]
    assert workflow_starter.calls == [{"task_id": "2001"}]


def test_async_create_patrol_task_uses_async_repository_and_starts_workflow():
    repository = FakePatrolTaskRepository(
        response={
            "result_code": "ACCEPTED",
            "task_id": 2001,
            "task_status": "WAITING_DISPATCH",
            "assigned_robot_id": "pinky3",
        }
    )
    workflow_starter = FakeWorkflowStarter()
    service = PatrolTaskCreateService(
        repository=repository,
        patrol_workflow_starter=workflow_starter,
    )

    response = asyncio.run(service.async_create_patrol_task(**build_patrol_payload()))

    assert response["result_code"] == "ACCEPTED"
    assert repository.calls == [build_patrol_payload()]
    assert workflow_starter.calls == [{"task_id": "2001"}]


def test_create_patrol_task_rejects_invalid_payload_before_repository_call():
    repository = FakePatrolTaskRepository(response={"result_code": "ACCEPTED"})
    workflow_starter = FakeWorkflowStarter()
    service = PatrolTaskCreateService(
        repository=repository,
        patrol_workflow_starter=workflow_starter,
    )

    response = service.create_patrol_task(
        request_id="req_patrol_001",
        caregiver_id="1",
        patrol_area_id="",
        priority="NORMAL",
        idempotency_key="idem_patrol_001",
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "PATROL_AREA_ID_INVALID"
    assert repository.calls == []
    assert workflow_starter.calls == []
