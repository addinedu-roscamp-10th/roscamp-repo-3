import asyncio

from server.ropi_main_service.application.patrol_config import PatrolRuntimeConfig
from server.ropi_main_service.persistence.repositories.patrol_task_create_repository import (
    PATROL_CREATE_SCOPE,
    PatrolPathSnapshotBuilder,
    PatrolTaskCreateRepository,
)


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def begin(self):
        pass

    def cursor(self):
        return FakeCursor()

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeAsyncTransaction:
    def __init__(self):
        self.cursor = FakeCursor()
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self.cursor

    async def __aexit__(self, exc_type, exc, tb):
        self.exited = True
        return False


class FakeIdempotencyRepository:
    def __init__(self):
        self.find_args = None
        self.inserted = None

    def build_request_hash(self, **payload):
        self.hash_payload = payload
        return "patrol_request_hash"

    def find_response(self, cur, **kwargs):
        self.find_args = kwargs
        return None

    async def async_find_response(self, cur, **kwargs):
        self.find_args = kwargs
        return None

    def insert_record(self, cur, **kwargs):
        self.inserted = kwargs

    async def async_insert_record(self, cur, **kwargs):
        self.inserted = kwargs


class FakePatrolTaskRepository:
    def __init__(self):
        self.created = None

    def create_patrol_task_records(self, cur, **kwargs):
        self.created = kwargs
        return 2001

    async def async_create_patrol_task_records(self, cur, **kwargs):
        self.created = kwargs
        return 2001


def _build_patrol_area():
    return {
        "patrol_area_id": "patrol_ward_night_01",
        "patrol_area_name": "야간 병동 순찰",
        "revision": 7,
        "map_id": "map_test11_0423",
        "path_json": {
            "header": {"frame_id": "map"},
            "poses": [{"pose": {"position": {"x": 1.0, "y": 2.0}}}],
        },
        "is_enabled": 1,
    }


def test_patrol_task_create_repository_creates_sync_patrol_task_records():
    fake_conn = FakeConnection()
    idempotency_repository = FakeIdempotencyRepository()
    patrol_task_repository = FakePatrolTaskRepository()
    repository = PatrolTaskCreateRepository(
        runtime_config=PatrolRuntimeConfig(pinky_id="pinky7"),
        patrol_task_repository=patrol_task_repository,
        idempotency_repository=idempotency_repository,
        connection_factory=lambda: fake_conn,
        caregiver_exists=lambda cur, caregiver_id: True,
        fetch_patrol_area_by_id=lambda cur, patrol_area_id: _build_patrol_area(),
    )

    response = repository.create_patrol_task(
        request_id="req_patrol_001",
        caregiver_id="caregiver-1",
        patrol_area_id="patrol_ward_night_01",
        priority="NORMAL",
        idempotency_key="idem_patrol_001",
    )

    assert response == {
        "result_code": "ACCEPTED",
        "result_message": None,
        "reason_code": None,
        "task_id": 2001,
        "task_status": "WAITING_DISPATCH",
        "assigned_robot_id": "pinky7",
        "patrol_area_id": "patrol_ward_night_01",
        "patrol_area_name": "야간 병동 순찰",
        "patrol_area_revision": 7,
    }
    assert patrol_task_repository.created["caregiver_id"] == 1
    assert patrol_task_repository.created["assigned_robot_id"] == "pinky7"
    assert patrol_task_repository.created["frame_id"] == "map"
    assert patrol_task_repository.created["waypoint_count"] == 1
    assert idempotency_repository.find_args["scope"] == PATROL_CREATE_SCOPE
    assert idempotency_repository.inserted["scope"] == PATROL_CREATE_SCOPE
    assert fake_conn.committed is True
    assert fake_conn.closed is True


def test_patrol_task_create_repository_creates_async_patrol_task_records():
    fake_transaction = FakeAsyncTransaction()
    idempotency_repository = FakeIdempotencyRepository()
    patrol_task_repository = FakePatrolTaskRepository()

    async def async_caregiver_exists(cur, caregiver_id):
        return True

    async def async_fetch_patrol_area_by_id(cur, patrol_area_id):
        return _build_patrol_area()

    repository = PatrolTaskCreateRepository(
        runtime_config=PatrolRuntimeConfig(pinky_id="pinky7"),
        patrol_task_repository=patrol_task_repository,
        idempotency_repository=idempotency_repository,
        async_transaction_factory=lambda: fake_transaction,
        async_caregiver_exists=async_caregiver_exists,
        async_fetch_patrol_area_by_id=async_fetch_patrol_area_by_id,
    )

    response = asyncio.run(
        repository.async_create_patrol_task(
            request_id="req_patrol_001",
            caregiver_id=1,
            patrol_area_id="patrol_ward_night_01",
            priority="URGENT",
            idempotency_key="idem_patrol_001",
        )
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["assigned_robot_id"] == "pinky7"
    assert patrol_task_repository.created["priority"] == "URGENT"
    assert idempotency_repository.inserted["task_id"] == 2001
    assert fake_transaction.entered is True
    assert fake_transaction.exited is True


def test_patrol_path_snapshot_builder_rejects_missing_waypoints():
    area = _build_patrol_area()
    area["path_json"] = {"header": {"frame_id": "map"}, "poses": []}

    response = PatrolTaskCreateRepository.validate_patrol_area_for_create(area)

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "PATROL_PATH_CONFIG_MISSING"
    assert "waypoint" in response["result_message"]


def test_patrol_path_snapshot_builder_accepts_json_string_path():
    area = _build_patrol_area()
    area["path_json"] = '{"header":{"frame_id":"odom"},"poses":[{"x":1,"y":2}]}'

    snapshot = PatrolPathSnapshotBuilder.build(area)

    assert snapshot["frame_id"] == "odom"
    assert snapshot["waypoint_count"] == 1
    assert snapshot["path_json"]["poses"] == [{"x": 1, "y": 2}]
