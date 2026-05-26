import asyncio

from server.ropi_main_service.application.drive_config import DriveRuntimeConfig
from server.ropi_main_service.persistence.repositories.drive_task_create_repository import (
    DRIVE_CREATE_SCOPE,
    DriveRouteSnapshotBuilder,
    DriveTaskCreateRepository,
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
        return "drive_request_hash"

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


class FakeDriveTaskRepository:
    def __init__(self):
        self.created = None

    def create_drive_task_records(self, cur, **kwargs):
        self.created = kwargs
        return 3001

    async def async_create_drive_task_records(self, cur, **kwargs):
        self.created = kwargs
        return 3001


def _build_route():
    return {
        "route_id": "corridor_round_trip",
        "route_name": "복도 왕복",
        "route_scope": "COMMON",
        "revision": 4,
        "map_id": "map_0504",
        "is_enabled": 1,
        "waypoint_sequence": [
            {
                "sequence_no": 1,
                "waypoint_id": "hall_a",
                "yaw_policy": "FIXED",
                "fixed_pose_yaw": 0.5,
                "stop_required": True,
                "dwell_sec": 0.0,
                "pose_x": 1.0,
                "pose_y": 2.0,
                "pose_yaw": 0.0,
                "frame_id": "map",
            },
            {
                "sequence_no": 2,
                "waypoint_id": "hall_b",
                "yaw_policy": "AUTO_NEXT",
                "fixed_pose_yaw": None,
                "stop_required": True,
                "dwell_sec": 0.0,
                "pose_x": 3.0,
                "pose_y": 4.0,
                "pose_yaw": 1.0,
                "frame_id": "map",
            },
        ],
    }


def test_drive_task_create_repository_creates_sync_drive_task_records():
    fake_conn = FakeConnection()
    idempotency_repository = FakeIdempotencyRepository()
    drive_task_repository = FakeDriveTaskRepository()
    repository = DriveTaskCreateRepository(
        runtime_config=DriveRuntimeConfig(map_id="map_0504"),
        drive_task_repository=drive_task_repository,
        idempotency_repository=idempotency_repository,
        connection_factory=lambda: fake_conn,
        caregiver_exists=lambda cur, caregiver_id: True,
        fetch_route_by_id=lambda cur, route_id: _build_route(),
    )

    response = repository.create_drive_task(
        request_id="req_drive_001",
        caregiver_id="caregiver-1",
        robot_id="pinky1",
        route_id="corridor_round_trip",
        priority="NORMAL",
        notes="first FMS test",
        idempotency_key="idem_drive_001",
    )

    assert response == {
        "result_code": "ACCEPTED",
        "result_message": None,
        "reason_code": None,
        "task_id": 3001,
        "task_type": "DRIVE",
        "task_status": "WAITING_DISPATCH",
        "phase": "REQUESTED",
        "assigned_robot_id": "pinky1",
        "map_id": "map_0504",
        "route_id": "corridor_round_trip",
        "route_name": "복도 왕복",
        "route_revision": 4,
        "waypoint_count": 2,
    }
    assert drive_task_repository.created["caregiver_id"] == 1
    assert drive_task_repository.created["assigned_robot_id"] == "pinky1"
    assert drive_task_repository.created["frame_id"] == "map"
    assert drive_task_repository.created["waypoint_count"] == 2
    assert drive_task_repository.created["path_snapshot_json"]["poses"][0]["yaw"] == 0.5
    assert idempotency_repository.find_args["scope"] == DRIVE_CREATE_SCOPE
    assert idempotency_repository.inserted["scope"] == DRIVE_CREATE_SCOPE
    assert fake_conn.committed is True
    assert fake_conn.closed is True


def test_drive_task_create_repository_auto_assigns_robot_when_robot_id_is_omitted():
    fake_conn = FakeConnection()
    drive_task_repository = FakeDriveTaskRepository()
    repository = DriveTaskCreateRepository(
        runtime_config=DriveRuntimeConfig(
            map_id="map_0504",
            robot_ids=("pinky1", "pinky3"),
        ),
        drive_task_repository=drive_task_repository,
        idempotency_repository=FakeIdempotencyRepository(),
        connection_factory=lambda: fake_conn,
        caregiver_exists=lambda cur, caregiver_id: True,
        fetch_route_by_id=lambda cur, route_id: _build_route(),
        select_robot_id=lambda cur: "pinky3",
    )

    response = repository.create_drive_task(
        request_id="req_drive_001",
        caregiver_id=1,
        robot_id=None,
        route_id="corridor_round_trip",
        priority="NORMAL",
        notes=None,
        idempotency_key="idem_drive_001",
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["assigned_robot_id"] == "pinky3"
    assert drive_task_repository.created["assigned_robot_id"] == "pinky3"


def test_drive_task_create_repository_rejects_when_auto_assignment_has_no_robot():
    fake_conn = FakeConnection()
    drive_task_repository = FakeDriveTaskRepository()
    repository = DriveTaskCreateRepository(
        runtime_config=DriveRuntimeConfig(map_id="map_0504", robot_ids=()),
        drive_task_repository=drive_task_repository,
        idempotency_repository=FakeIdempotencyRepository(),
        connection_factory=lambda: fake_conn,
        caregiver_exists=lambda cur, caregiver_id: True,
        fetch_route_by_id=lambda cur, route_id: _build_route(),
        select_robot_id=lambda cur: None,
    )

    response = repository.create_drive_task(
        request_id="req_drive_001",
        caregiver_id=1,
        robot_id="AUTO",
        route_id="corridor_round_trip",
        priority="NORMAL",
        notes=None,
        idempotency_key="idem_drive_001",
    )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "DRIVE_ROBOT_NOT_AVAILABLE"
    assert drive_task_repository.created is None
    assert fake_conn.rolled_back is True


def test_drive_task_create_repository_auto_assignment_prefers_fewer_active_drive_tasks():
    selected = DriveTaskCreateRepository._choose_robot_id(
        allowed_robot_ids=("pinky1", "pinky3"),
        existing_robot_ids={"pinky1", "pinky3"},
        active_counts={"pinky1": 1, "pinky3": 0},
    )

    assert selected == "pinky3"


def test_drive_task_create_repository_creates_async_drive_task_records():
    fake_transaction = FakeAsyncTransaction()
    idempotency_repository = FakeIdempotencyRepository()
    drive_task_repository = FakeDriveTaskRepository()

    async def async_caregiver_exists(cur, caregiver_id):
        return True

    async def async_fetch_route_by_id(cur, route_id):
        return _build_route()

    repository = DriveTaskCreateRepository(
        runtime_config=DriveRuntimeConfig(map_id="map_0504"),
        drive_task_repository=drive_task_repository,
        idempotency_repository=idempotency_repository,
        async_transaction_factory=lambda: fake_transaction,
        async_caregiver_exists=async_caregiver_exists,
        async_fetch_route_by_id=async_fetch_route_by_id,
    )

    response = asyncio.run(
        repository.async_create_drive_task(
            request_id="req_drive_001",
            caregiver_id=1,
            robot_id="pinky3",
            route_id="corridor_round_trip",
            priority="URGENT",
            notes=None,
            idempotency_key="idem_drive_001",
        )
    )

    assert response["result_code"] == "ACCEPTED"
    assert response["assigned_robot_id"] == "pinky3"
    assert drive_task_repository.created["priority"] == "URGENT"
    assert idempotency_repository.inserted["task_id"] == 3001
    assert fake_transaction.entered is True
    assert fake_transaction.exited is True


def test_drive_task_create_repository_rejects_robot_outside_runtime_config_before_db():
    repository = DriveTaskCreateRepository(
        runtime_config=DriveRuntimeConfig(
            map_id="map_0504",
            robot_ids=("pinky1", "pinky3"),
        ),
        connection_factory=lambda: (_ for _ in ()).throw(
            AssertionError("DB connection should not be opened")
        ),
    )

    response = repository.create_drive_task(
        request_id="req_drive_001",
        caregiver_id=1,
        robot_id="pinky9",
        route_id="corridor_round_trip",
        priority="NORMAL",
        notes=None,
        idempotency_key="idem_drive_001",
    )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "DRIVE_ROBOT_NOT_ALLOWED"


def test_drive_route_snapshot_builder_rejects_short_route():
    route = _build_route()
    route["waypoint_sequence"] = route["waypoint_sequence"][:1]
    repository = DriveTaskCreateRepository(
        runtime_config=DriveRuntimeConfig(map_id="map_0504")
    )

    response = repository.validate_route_for_create(route)

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "DRIVE_ROUTE_CONFIG_MISSING"
    assert "waypoint" in response["result_message"]


def test_drive_route_snapshot_builder_materializes_fixed_and_waypoint_yaw():
    snapshot = DriveRouteSnapshotBuilder.build(_build_route())

    assert snapshot["frame_id"] == "map"
    assert snapshot["waypoint_count"] == 2
    assert snapshot["path_json"]["poses"][0]["yaw"] == 0.5
    assert snapshot["path_json"]["poses"][1]["yaw"] == 1.0
