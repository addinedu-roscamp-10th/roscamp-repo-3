import asyncio

from server.ropi_main_service.application.drive_task_create import (
    DriveTaskCreateService,
)
from server.ropi_main_service.application.drive_config import DriveRuntimeConfig


class FakeDriveTaskRepository:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create_drive_task(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.response)

    async def async_create_drive_task(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.response)


class FakeWorkflowStarter:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


def build_drive_payload():
    return {
        "request_id": "req_drive_001",
        "caregiver_id": "1",
        "robot_id": "pinky1",
        "route_id": "corridor_round_trip",
        "priority": "NORMAL",
        "notes": "first FMS test",
        "idempotency_key": "idem_drive_001",
    }


def test_create_drive_task_validates_and_starts_workflow_after_acceptance():
    repository = FakeDriveTaskRepository(
        response={
            "result_code": "ACCEPTED",
            "task_id": 3001,
            "task_type": "DRIVE",
            "task_status": "WAITING_DISPATCH",
            "phase": "REQUESTED",
            "assigned_robot_id": "pinky1",
        }
    )
    workflow_starter = FakeWorkflowStarter()
    service = DriveTaskCreateService(
        repository=repository,
        drive_workflow_starter=workflow_starter,
    )

    response = service.create_drive_task(**build_drive_payload())

    assert response["result_code"] == "ACCEPTED"
    assert repository.calls == [build_drive_payload()]
    assert workflow_starter.calls == [{"task_id": "3001"}]


def test_async_create_drive_task_uses_async_repository_and_starts_workflow():
    repository = FakeDriveTaskRepository(
        response={
            "result_code": "ACCEPTED",
            "task_id": 3001,
            "task_type": "DRIVE",
            "task_status": "WAITING_DISPATCH",
            "phase": "REQUESTED",
            "assigned_robot_id": "pinky3",
        }
    )
    workflow_starter = FakeWorkflowStarter()
    service = DriveTaskCreateService(
        repository=repository,
        drive_workflow_starter=workflow_starter,
    )

    response = asyncio.run(service.async_create_drive_task(**build_drive_payload()))

    assert response["result_code"] == "ACCEPTED"
    assert repository.calls == [build_drive_payload()]
    assert workflow_starter.calls == [{"task_id": "3001"}]


def test_create_drive_task_rejects_ambiguous_robot_namespace():
    repository = FakeDriveTaskRepository(response={"result_code": "ACCEPTED"})
    service = DriveTaskCreateService(repository=repository)

    payload = build_drive_payload()
    payload["robot_id"] = "/pinky1"
    response = service.create_drive_task(**payload)

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "DRIVE_ROBOT_ID_INVALID"
    assert repository.calls == []


def test_create_drive_task_rejects_robot_outside_drive_runtime_config():
    repository = FakeDriveTaskRepository(response={"result_code": "ACCEPTED"})
    service = DriveTaskCreateService(
        repository=repository,
        runtime_config=DriveRuntimeConfig(robot_ids=("pinky1", "pinky3")),
    )

    payload = build_drive_payload()
    payload["robot_id"] = "pinky9"
    response = service.create_drive_task(**payload)

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "DRIVE_ROBOT_NOT_ALLOWED"
    assert repository.calls == []


def test_create_drive_task_rejects_invalid_payload_before_repository_call():
    repository = FakeDriveTaskRepository(response={"result_code": "ACCEPTED"})
    service = DriveTaskCreateService(repository=repository)

    payload = build_drive_payload()
    payload["route_id"] = ""
    response = service.create_drive_task(**payload)

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "DRIVE_ROUTE_ID_INVALID"
    assert repository.calls == []
