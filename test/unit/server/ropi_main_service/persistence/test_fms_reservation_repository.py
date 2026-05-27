from server.ropi_main_service.persistence.repositories.fms_reservation_repository import (
    FmsReservationRepository,
)


class FakeCursor:
    def __init__(self, *, rowcount=0, rows=None):
        self.calls = []
        self.rowcount = rowcount
        self.rows = list(rows or [])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        if not self.rows:
            return None
        return self.rows.pop(0)


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.began = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def begin(self):
        self.began = True

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_fms_reservation_repository_normalizes_conflict_zone_resource():
    normalized = FmsReservationRepository._normalize_resource(
        {
            "resource_type": "CONFLICT_ZONE",
            "resource_id": "cz_geo_cross_01",
        }
    )

    assert normalized == {
        "key": ("CONFLICT_ZONE", "cz_geo_cross_01"),
        "resource_type": "CONFLICT_ZONE",
        "resource_id": "cz_geo_cross_01",
        "waypoint_id": None,
        "edge_id": None,
        "conflict_zone_id": "cz_geo_cross_01",
    }


def test_fms_reservation_repository_release_by_task_and_robot_returns_rowcount():
    cursor = FakeCursor(rowcount=3)
    connection = FakeConnection(cursor)
    repository = FmsReservationRepository(connection_factory=lambda: connection)

    released_count = repository.release_reservation(
        task_id=771,
        robot_id="pinky1",
        reason_code="FAILED",
    )

    assert released_count == 3
    assert connection.began is True
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    assert cursor.calls[0][1] == ("FAILED", 771, "pinky1")


def test_request_reservation_reuses_same_task_waiting_row_when_conflict_remains():
    existing_blocker = {
        "reservation_id": "resv_other",
        "task_id": 99,
        "robot_id": "pinky3",
        "map_id": "map_0504",
        "resource_type": "WAYPOINT",
        "resource_id": "hall_1_1",
        "reservation_status": "HELD",
    }
    existing_waiting = {
        "reservation_id": "resv_waiting",
        "task_id": 771,
        "robot_id": "pinky1",
        "map_id": "map_0504",
        "resource_type": "WAYPOINT",
        "resource_id": "hall_1_1",
        "reservation_status": "WAITING",
    }
    cursor = FakeCursor(rows=[existing_blocker, existing_waiting])
    connection = FakeConnection(cursor)
    repository = FmsReservationRepository(connection_factory=lambda: connection)

    response = repository.request_reservation(
        task_id=771,
        robot_id="pinky1",
        map_id="map_0504",
        resources=[{"resource_type": "WAYPOINT", "resource_id": "hall_1_1"}],
        lease_sec=30,
    )

    assert response["reservation_status"] == "WAITING"
    assert response["reservations"] == [existing_waiting]
    assert not any(
        "INSERT INTO fms_reservation" in call[0] for call in cursor.calls
    )
    assert connection.committed is True


def test_request_reservation_promotes_same_task_waiting_row_when_conflict_clears():
    existing_waiting = {
        "reservation_id": "resv_waiting",
        "task_id": 771,
        "robot_id": "pinky1",
        "map_id": "map_0504",
        "resource_type": "WAYPOINT",
        "resource_id": "hall_1_1",
        "reservation_status": "WAITING",
    }
    promoted = {
        **existing_waiting,
        "reservation_status": "HELD",
    }
    cursor = FakeCursor(rows=[None, existing_waiting, promoted])
    connection = FakeConnection(cursor)
    repository = FmsReservationRepository(connection_factory=lambda: connection)

    response = repository.request_reservation(
        task_id=771,
        robot_id="pinky1",
        map_id="map_0504",
        resources=[{"resource_type": "WAYPOINT", "resource_id": "hall_1_1"}],
        lease_sec=30,
    )

    assert response["reservation_status"] == "HELD"
    assert response["reservations"] == [promoted]
    assert not any(
        "INSERT INTO fms_reservation" in call[0] for call in cursor.calls
    )
    assert any("UPDATE fms_reservation" in call[0] for call in cursor.calls)
    assert connection.committed is True
