import asyncio
from contextlib import asynccontextmanager

from server.ropi_main_service.persistence.repositories import fms_config_repository


class FakeCursor:
    def __init__(self, rows=None):
        self.calls = []
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
        self.cursor_obj = cursor
        self.began = False
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def begin(self):
        self.began = True

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_fms_config_repository_fetches_active_map_and_waypoints(monkeypatch):
    calls = []

    def fake_fetch_one(query, params=None):
        calls.append(("one", query, params))
        return {"map_id": "map_0504"}

    def fake_fetch_all(query, params=None):
        calls.append(("all", query, params))
        return [{"waypoint_id": "corridor_01"}]

    monkeypatch.setattr(fms_config_repository, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(fms_config_repository, "fetch_all", fake_fetch_all)

    repository = fms_config_repository.FmsConfigRepository()

    assert repository.get_active_map_profile() == {"map_id": "map_0504"}
    assert repository.get_waypoints(
        map_id="map_0504",
        include_disabled=False,
    ) == [{"waypoint_id": "corridor_01"}]

    assert calls == [
        ("one", fms_config_repository.ACTIVE_MAP_PROFILE_SQL, None),
        (
            "all",
            fms_config_repository.LIST_WAYPOINTS_SQL,
            ("map_0504", False),
        ),
    ]
    assert "FROM fms_waypoint" in fms_config_repository.LIST_WAYPOINTS_SQL


def test_fms_config_repository_inserts_missing_waypoint(monkeypatch):
    inserted_row = {
        "waypoint_id": "corridor_02",
        "map_id": "map_0504",
    }
    cursor = FakeCursor(rows=[None, inserted_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(fms_config_repository, "get_connection", lambda: connection)

    result = fms_config_repository.FmsConfigRepository().upsert_waypoint(
        map_id="map_0504",
        waypoint_id="corridor_02",
        expected_updated_at=None,
        display_name="복도2",
        waypoint_type="CORRIDOR",
        pose_x=0.42,
        pose_y=-0.52,
        pose_yaw=0.0,
        frame_id="map",
        snap_group="main_corridor",
        is_enabled=True,
    )

    assert result == {"status": "UPSERTED", "waypoint": inserted_row}
    assert connection.began is True
    assert connection.committed is True
    lock_query, lock_params = cursor.calls[0]
    insert_query, insert_params = cursor.calls[1]
    select_query, select_params = cursor.calls[2]
    assert lock_query == fms_config_repository.LOCK_WAYPOINT_SQL
    assert lock_params == ("corridor_02",)
    assert "INSERT INTO fms_waypoint" in insert_query
    assert insert_params == (
        "corridor_02",
        "map_0504",
        "복도2",
        "CORRIDOR",
        0.42,
        -0.52,
        0.0,
        "map",
        "main_corridor",
        True,
    )
    assert select_query == fms_config_repository.FIND_WAYPOINT_SQL
    assert select_params == ("corridor_02",)


def test_fms_config_repository_updates_existing_waypoint_with_stale_check(monkeypatch):
    locked_row = {
        "waypoint_id": "corridor_01",
        "map_id": "map_0504",
        "updated_at": "2026-05-04T10:01:00",
    }
    updated_row = {
        "waypoint_id": "corridor_01",
        "map_id": "map_0504",
    }
    cursor = FakeCursor(rows=[locked_row, updated_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(fms_config_repository, "get_connection", lambda: connection)

    result = fms_config_repository.FmsConfigRepository().upsert_waypoint(
        map_id="map_0504",
        waypoint_id="corridor_01",
        expected_updated_at="2026-05-04T10:01:00",
        display_name="복도1",
        waypoint_type="CORRIDOR",
        pose_x=0.12,
        pose_y=-0.34,
        pose_yaw=1.57,
        frame_id="map",
        snap_group=None,
        is_enabled=False,
    )

    assert result == {"status": "UPSERTED", "waypoint": updated_row}
    update_query, update_params = cursor.calls[1]
    assert "UPDATE fms_waypoint" in update_query
    assert update_params == (
        "복도1",
        "CORRIDOR",
        0.12,
        -0.34,
        1.57,
        "map",
        None,
        False,
        "corridor_01",
        "map_0504",
    )


def test_fms_config_repository_reports_waypoint_stale_conflict(monkeypatch):
    locked_row = {
        "waypoint_id": "corridor_01",
        "map_id": "map_0504",
        "updated_at": "2026-05-04T10:01:00",
    }
    cursor = FakeCursor(rows=[locked_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(fms_config_repository, "get_connection", lambda: connection)

    result = fms_config_repository.FmsConfigRepository().upsert_waypoint(
        map_id="map_0504",
        waypoint_id="corridor_01",
        expected_updated_at="2026-05-04T09:59:00",
        display_name="복도1",
        waypoint_type="CORRIDOR",
        pose_x=0.12,
        pose_y=-0.34,
        pose_yaw=1.57,
        frame_id="map",
        snap_group=None,
        is_enabled=True,
    )

    assert result == {"status": "STALE", "waypoint": locked_row}
    assert len(cursor.calls) == 1


def test_fms_config_repository_exposes_async_methods(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append(("one", query, params))
        return {"map_id": "map_0504"}

    async def fake_async_fetch_all(query, params=None):
        calls.append(("all", query, params))
        return [{"waypoint_id": "corridor_01"}]

    monkeypatch.setattr(
        fms_config_repository,
        "async_fetch_one",
        fake_async_fetch_one,
    )
    monkeypatch.setattr(
        fms_config_repository,
        "async_fetch_all",
        fake_async_fetch_all,
    )

    async def scenario():
        repository = fms_config_repository.FmsConfigRepository()
        active_map = await repository.async_get_active_map_profile()
        waypoints = await repository.async_get_waypoints(
            map_id="map_0504",
            include_disabled=True,
        )
        return active_map, waypoints

    active_map, waypoints = asyncio.run(scenario())

    assert active_map == {"map_id": "map_0504"}
    assert waypoints == [{"waypoint_id": "corridor_01"}]
    assert calls == [
        ("one", fms_config_repository.ACTIVE_MAP_PROFILE_SQL, None),
        ("all", fms_config_repository.LIST_WAYPOINTS_SQL, ("map_0504", True)),
    ]


def test_fms_config_repository_async_upsert_waypoint(monkeypatch):
    locked_row = None
    inserted_row = {
        "waypoint_id": "corridor_02",
        "map_id": "map_0504",
    }
    calls = []

    class AsyncCursor:
        def __init__(self):
            self.rows = [locked_row, inserted_row]

        async def execute(self, query, params=None):
            calls.append((query, params))

        async def fetchone(self):
            if not self.rows:
                return None
            return self.rows.pop(0)

    @asynccontextmanager
    async def fake_async_transaction():
        yield AsyncCursor()

    monkeypatch.setattr(
        fms_config_repository,
        "async_transaction",
        fake_async_transaction,
    )

    async def scenario():
        return await fms_config_repository.FmsConfigRepository().async_upsert_waypoint(
            map_id="map_0504",
            waypoint_id="corridor_02",
            expected_updated_at=None,
            display_name="복도2",
            waypoint_type="CORRIDOR",
            pose_x=0.42,
            pose_y=-0.52,
            pose_yaw=0.0,
            frame_id="map",
            snap_group=None,
            is_enabled=True,
        )

    result = asyncio.run(scenario())

    assert result == {"status": "UPSERTED", "waypoint": inserted_row}
    assert calls[0] == (fms_config_repository.LOCK_WAYPOINT_SQL, ("corridor_02",))
    assert "INSERT INTO fms_waypoint" in calls[1][0]
    assert calls[2] == (fms_config_repository.FIND_WAYPOINT_SQL, ("corridor_02",))
