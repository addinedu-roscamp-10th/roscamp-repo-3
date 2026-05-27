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


class FakeDriveRobotReadinessService:
    def __init__(self, *, available_robot_ids=None, ready_by_robot=None):
        self.available_robot_ids_result = available_robot_ids
        self.ready_by_robot = ready_by_robot or {}
        self.available_calls = []
        self.ready_calls = []

    def available_robot_ids(self, robot_ids):
        self.available_calls.append(tuple(robot_ids))
        return self.available_robot_ids_result

    async def async_available_robot_ids(self, robot_ids):
        self.available_calls.append(tuple(robot_ids))
        return self.available_robot_ids_result

    def is_robot_ready(self, robot_id):
        self.ready_calls.append(robot_id)
        return self.ready_by_robot.get(robot_id)

    async def async_is_robot_ready(self, robot_id):
        self.ready_calls.append(robot_id)
        return self.ready_by_robot.get(robot_id)


def build_drive_payload():
    return {
        "request_id": "req_drive_001",
        "caregiver_id": "1",
        "robot_id": None,
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
        drive_robot_readiness_service=FakeDriveRobotReadinessService(),
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
        drive_robot_readiness_service=FakeDriveRobotReadinessService(),
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


def test_create_drive_task_accepts_explicit_allowed_robot_namespace():
    repository = FakeDriveTaskRepository(response={"result_code": "ACCEPTED"})
    service = DriveTaskCreateService(
        repository=repository,
        runtime_config=DriveRuntimeConfig(robot_ids=("pinky1", "pinky3")),
        drive_robot_readiness_service=FakeDriveRobotReadinessService(),
    )

    payload = build_drive_payload()
    payload["robot_id"] = "pinky1"
    response = service.create_drive_task(**payload)

    assert response["result_code"] == "ACCEPTED"
    assert repository.calls == [payload]


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


def test_create_drive_task_auto_assignment_uses_ready_nav2_robot_candidates():
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
    readiness = FakeDriveRobotReadinessService(available_robot_ids=("pinky3",))
    service = DriveTaskCreateService(
        repository=repository,
        runtime_config=DriveRuntimeConfig(robot_ids=("pinky1", "pinky3")),
        drive_robot_readiness_service=readiness,
    )

    response = service.create_drive_task(**build_drive_payload())

    assert response["result_code"] == "ACCEPTED"
    assert readiness.available_calls == [("pinky1", "pinky3")]
    assert repository.calls == [
        {
            **build_drive_payload(),
            "candidate_robot_ids": ("pinky3",),
        }
    ]


def test_create_drive_task_rejects_auto_when_no_nav2_robot_is_ready():
    repository = FakeDriveTaskRepository(response={"result_code": "ACCEPTED"})
    readiness = FakeDriveRobotReadinessService(available_robot_ids=())
    service = DriveTaskCreateService(
        repository=repository,
        runtime_config=DriveRuntimeConfig(robot_ids=("pinky1", "pinky3")),
        drive_robot_readiness_service=readiness,
    )

    response = service.create_drive_task(**build_drive_payload())

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "DRIVE_ROBOT_NOT_AVAILABLE"
    assert repository.calls == []


def test_create_drive_task_rejects_explicit_robot_without_ready_nav2_action():
    repository = FakeDriveTaskRepository(response={"result_code": "ACCEPTED"})
    readiness = FakeDriveRobotReadinessService(ready_by_robot={"pinky1": False})
    service = DriveTaskCreateService(
        repository=repository,
        runtime_config=DriveRuntimeConfig(robot_ids=("pinky1", "pinky3")),
        drive_robot_readiness_service=readiness,
    )

    payload = build_drive_payload()
    payload["robot_id"] = "pinky1"
    response = service.create_drive_task(**payload)

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "DRIVE_ROBOT_NOT_AVAILABLE"
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
