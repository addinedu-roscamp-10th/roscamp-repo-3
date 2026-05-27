from server.ropi_main_service.persistence.repositories.fms_reservation_repository import (
    FmsReservationRepository,
)


class FakeCursor:
    def __init__(self, *, rowcount=0):
        self.calls = []
        self.rowcount = rowcount

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))


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
