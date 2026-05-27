from datetime import datetime, timezone

from server.ropi_main_service.application.fms_runtime import FmsRuntimeService


class FakeFmsReservationRepository:
    def __init__(self):
        self.requested = None
        self.renewed = None
        self.released = None
        self.snapshot_map_id = None
        self.request_result = {
            "reservation_status": "HELD",
            "reason_code": None,
            "reservations": [
                {
                    "reservation_id": "resv_001",
                    "task_id": 3001,
                    "robot_id": "pinky1",
                    "map_id": "map_0504",
                    "resource_type": "EDGE",
                    "resource_id": "edge_corridor_01_02",
                    "reservation_status": "HELD",
                    "reserved_from": datetime(2026, 5, 4, 10, 10, 0),
                    "reserved_until": datetime(2026, 5, 4, 10, 10, 30),
                    "reason_code": None,
                }
            ],
        }
        self.release_count = 2
        self.renew_count = 2
        self.reservations = list(self.request_result["reservations"])

    def request_reservation(self, **kwargs):
        self.requested = kwargs
        return self.request_result

    def release_reservation(self, **kwargs):
        self.released = kwargs
        return self.release_count

    def renew_reservation(self, **kwargs):
        self.renewed = kwargs
        return self.renew_count

    def get_reservation_snapshot(self, *, map_id=None):
        self.snapshot_map_id = map_id
        return self.reservations


def test_fms_runtime_request_reservation_returns_held_snapshot():
    repository = FakeFmsReservationRepository()
    service = FmsRuntimeService(
        repository=repository,
        clock=lambda: datetime(2026, 5, 4, 1, 2, 3, tzinfo=timezone.utc),
    )

    response = service.request_reservation(
        task_id=3001,
        robot_id="pinky1",
        map_id="map_0504",
        resources=[
            {"resource_type": "EDGE", "resource_id": "edge_corridor_01_02"},
        ],
        lease_sec=30,
    )

    assert response == {
        "result_code": "HELD",
        "result_message": None,
        "reason_code": None,
        "generated_at": "2026-05-04T01:02:03+00:00",
        "reservation_status": "HELD",
        "task_id": 3001,
        "robot_id": "pinky1",
        "map_id": "map_0504",
        "reservations": [
            {
                "reservation_id": "resv_001",
                "task_id": 3001,
                "robot_id": "pinky1",
                "resource_type": "EDGE",
                "resource_id": "edge_corridor_01_02",
                "status": "HELD",
                "reserved_from": "2026-05-04T10:10:00",
                "reserved_until": "2026-05-04T10:10:30",
                "reason_code": None,
            }
        ],
        "next_task_phase": None,
    }
    assert repository.requested == {
        "task_id": 3001,
        "robot_id": "pinky1",
        "map_id": "map_0504",
        "resources": [
            {"resource_type": "EDGE", "resource_id": "edge_corridor_01_02"},
        ],
        "lease_sec": 30,
    }


def test_fms_runtime_request_reservation_returns_waiting_phase_on_conflict():
    repository = FakeFmsReservationRepository()
    repository.request_result = {
        "reservation_status": "WAITING",
        "reason_code": "FMS_RESOURCE_ALREADY_HELD",
        "reservations": [
            {
                "reservation_id": "resv_wait_001",
                "task_id": 3002,
                "robot_id": "pinky3",
                "map_id": "map_0504",
                "resource_type": "EDGE",
                "resource_id": "edge_corridor_01_02",
                "reservation_status": "WAITING",
                "reserved_from": None,
                "reserved_until": None,
                "reason_code": "FMS_RESOURCE_ALREADY_HELD",
            }
        ],
    }
    service = FmsRuntimeService(repository=repository)

    response = service.request_reservation(
        task_id=3002,
        robot_id="pinky3",
        map_id="map_0504",
        resources=[
            {"resource_type": "EDGE", "resource_id": "edge_corridor_01_02"},
        ],
    )

    assert response["result_code"] == "WAITING"
    assert response["reservation_status"] == "WAITING"
    assert response["reason_code"] == "FMS_RESOURCE_ALREADY_HELD"
    assert response["next_task_phase"] == "WAITING_FMS_RESERVATION"
    assert response["reservations"][0]["status"] == "WAITING"


def test_fms_runtime_release_reservation_returns_released_count():
    repository = FakeFmsReservationRepository()
    service = FmsRuntimeService(repository=repository)

    response = service.release_reservation(
        task_id=3001,
        robot_id="pinky1",
        reason_code="ARRIVED",
    )

    assert response["result_code"] == "RELEASED"
    assert response["released_count"] == 2
    assert repository.released == {
        "task_id": 3001,
        "robot_id": "pinky1",
        "reason_code": "ARRIVED",
        "resources": None,
    }


def test_fms_runtime_release_reservation_can_target_specific_resources():
    repository = FakeFmsReservationRepository()
    service = FmsRuntimeService(repository=repository)

    response = service.release_reservation(
        task_id=3001,
        robot_id="pinky1",
        reason_code="SEGMENT_COMPLETED",
        resources=[
            {"resource_type": "WAYPOINT", "resource_id": "corridor_01"},
            {"resource_type": "EDGE", "resource_id": "edge_corridor_01_02"},
        ],
    )

    assert response["result_code"] == "RELEASED"
    assert repository.released == {
        "task_id": 3001,
        "robot_id": "pinky1",
        "reason_code": "SEGMENT_COMPLETED",
        "resources": [
            {"resource_type": "WAYPOINT", "resource_id": "corridor_01"},
            {"resource_type": "EDGE", "resource_id": "edge_corridor_01_02"},
        ],
    }


def test_fms_runtime_renew_reservation_returns_renewed_count():
    repository = FakeFmsReservationRepository()
    service = FmsRuntimeService(
        repository=repository,
        clock=lambda: datetime(2026, 5, 4, 1, 2, 3, tzinfo=timezone.utc),
    )

    response = service.renew_reservation(
        task_id=3001,
        robot_id="pinky1",
        lease_sec=45,
    )

    assert response == {
        "result_code": "RENEWED",
        "result_message": None,
        "reason_code": None,
        "generated_at": "2026-05-04T01:02:03+00:00",
        "renewed_count": 2,
        "task_id": 3001,
    }
    assert repository.renewed == {
        "task_id": 3001,
        "robot_id": "pinky1",
        "lease_sec": 45,
    }


def test_fms_runtime_get_reservation_snapshot_formats_rows():
    repository = FakeFmsReservationRepository()
    service = FmsRuntimeService(
        repository=repository,
        clock=lambda: datetime(2026, 5, 4, 1, 2, 3, tzinfo=timezone.utc),
    )

    response = service.get_reservation_snapshot(map_id="map_0504")

    assert response["result_code"] == "OK"
    assert response["generated_at"] == "2026-05-04T01:02:03+00:00"
    assert response["reservations"][0]["reservation_id"] == "resv_001"
    assert repository.snapshot_map_id == "map_0504"


def test_fms_runtime_request_reservation_rejects_invalid_resource():
    repository = FakeFmsReservationRepository()
    service = FmsRuntimeService(repository=repository)

    response = service.request_reservation(
        task_id=3001,
        robot_id="pinky1",
        map_id="map_0504",
        resources=[{"resource_type": "ZONE", "resource_id": "bad"}],
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "FMS_RESOURCE_INVALID"
    assert repository.requested is None
