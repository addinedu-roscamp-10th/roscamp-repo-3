import asyncio
from contextlib import asynccontextmanager

from server.ropi_main_service.persistence.repositories import (
    coordinate_config_repository,
)


def test_coordinate_config_repository_fetches_active_map_and_child_rows(monkeypatch):
    calls = []

    def fake_fetch_one(query, params=None):
        calls.append(("one", query, params))
        return {"map_id": "map_test11_0423"}

    def fake_fetch_all(query, params=None):
        calls.append(("all", query, params))
        return [{"ok": True}]

    monkeypatch.setattr(coordinate_config_repository, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(coordinate_config_repository, "fetch_all", fake_fetch_all)

    repository = coordinate_config_repository.CoordinateConfigRepository()

    assert repository.get_active_map_profile() == {"map_id": "map_test11_0423"}
    assert repository.get_operation_zones(
        map_id="map_test11_0423",
        include_disabled=False,
    ) == [{"ok": True}]
    assert repository.get_goal_poses(
        map_id="map_test11_0423",
        include_disabled=True,
    ) == [{"ok": True}]
    assert repository.get_patrol_areas(
        map_id="map_test11_0423",
        include_disabled=False,
    ) == [{"ok": True}]

    assert calls[0][0] == "one"
    assert "FROM map_profile" in calls[0][1]
    assert calls[0][2] is None
    assert calls[1][0] == "all"
    assert "FROM operation_zone" in calls[1][1]
    assert "boundary_json" in calls[1][1]
    assert calls[1][2] == ("map_test11_0423", False)
    assert calls[2][0] == "all"
    assert "FROM goal_pose" in calls[2][1]
    assert "LEFT JOIN operation_zone" in calls[2][1]
    assert calls[2][2] == ("map_test11_0423", True)
    assert calls[3][0] == "all"
    assert "FROM patrol_area" in calls[3][1]
    assert "JSON_LENGTH(path_json, '$.poses')" in calls[3][1]
    assert calls[3][2] == ("map_test11_0423", False)


def test_coordinate_config_repository_fetches_map_profile_by_id(monkeypatch):
    calls = []

    def fake_fetch_one(query, params=None):
        calls.append((query, params))
        return {"map_id": "map_test11_0423"}

    monkeypatch.setattr(coordinate_config_repository, "fetch_one", fake_fetch_one)

    row = coordinate_config_repository.CoordinateConfigRepository().get_map_profile(
        map_id="map_test11_0423",
    )

    assert row == {"map_id": "map_test11_0423"}
    assert calls == [
        (
            coordinate_config_repository.FIND_MAP_PROFILE_SQL,
            ("map_test11_0423",),
        )
    ]


def test_coordinate_config_repository_fetches_operation_zone_by_map_and_zone(monkeypatch):
    calls = []

    def fake_fetch_one(query, params=None):
        calls.append((query, params))
        return {"map_id": "map_test12_0506", "zone_id": "room_301"}

    monkeypatch.setattr(coordinate_config_repository, "fetch_one", fake_fetch_one)

    row = coordinate_config_repository.CoordinateConfigRepository().get_operation_zone(
        map_id="map_test12_0506",
        zone_id="room_301",
    )

    assert row == {"map_id": "map_test12_0506", "zone_id": "room_301"}
    assert calls == [
        (
            coordinate_config_repository.FIND_OPERATION_ZONE_SQL,
            ("map_test12_0506", "room_301"),
        )
    ]


def test_coordinate_config_repository_exposes_async_fetch_methods(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append(("one", query, params))
        return {"map_id": "map_test11_0423"}

    async def fake_async_fetch_all(query, params=None):
        calls.append(("all", query, params))
        return [{"ok": True}]

    monkeypatch.setattr(
        coordinate_config_repository,
        "async_fetch_one",
        fake_async_fetch_one,
    )
    monkeypatch.setattr(
        coordinate_config_repository,
        "async_fetch_all",
        fake_async_fetch_all,
    )

    async def scenario():
        repository = coordinate_config_repository.CoordinateConfigRepository()
        active_map = await repository.async_get_active_map_profile()
        zones = await repository.async_get_operation_zones(
            map_id="map_test11_0423",
            include_disabled=False,
        )
        goals = await repository.async_get_goal_poses(
            map_id="map_test11_0423",
            include_disabled=False,
        )
        patrol_areas = await repository.async_get_patrol_areas(
            map_id="map_test11_0423",
            include_disabled=False,
        )
        return active_map, zones, goals, patrol_areas

    active_map, zones, goals, patrol_areas = asyncio.run(scenario())

    assert active_map == {"map_id": "map_test11_0423"}
    assert zones == [{"ok": True}]
    assert goals == [{"ok": True}]
    assert patrol_areas == [{"ok": True}]
    assert calls == [
        ("one", coordinate_config_repository.ACTIVE_MAP_PROFILE_SQL, None),
        (
            "all",
            coordinate_config_repository.LIST_OPERATION_ZONES_SQL,
            ("map_test11_0423", False),
        ),
        (
            "all",
            coordinate_config_repository.LIST_GOAL_POSES_SQL,
            ("map_test11_0423", False),
        ),
        (
            "all",
            coordinate_config_repository.LIST_PATROL_AREAS_SQL,
            ("map_test11_0423", False),
        ),
    ]


def test_coordinate_config_repository_fetches_map_profile_by_id_async(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append((query, params))
        return {"map_id": "map_test11_0423"}

    monkeypatch.setattr(
        coordinate_config_repository,
        "async_fetch_one",
        fake_async_fetch_one,
    )

    async def scenario():
        return await coordinate_config_repository.CoordinateConfigRepository().async_get_map_profile(
            map_id="map_test11_0423",
        )

    row = asyncio.run(scenario())

    assert row == {"map_id": "map_test11_0423"}
    assert calls == [
        (
            coordinate_config_repository.FIND_MAP_PROFILE_SQL,
            ("map_test11_0423",),
        )
    ]


class FakeCursor:
    def __init__(self, rows=None):
        self.calls = []
        self.rows = list(rows or [])
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.calls.append((query, params))
        self.rowcount = 1

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


def test_coordinate_config_repository_creates_operation_zone_in_transaction(
    monkeypatch,
):
    inserted_row = {
        "zone_id": "caregiver_room",
        "map_id": "map_test11_0423",
        "zone_name": "보호사실",
        "zone_type": "STAFF_STATION",
    }
    cursor = FakeCursor(rows=[inserted_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )

    row = coordinate_config_repository.CoordinateConfigRepository().create_operation_zone(
        map_id="map_test11_0423",
        zone_id="caregiver_room",
        zone_name="보호사실",
        zone_type="STAFF_STATION",
        is_enabled=True,
    )

    assert row == inserted_row
    assert connection.began is True
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True
    insert_query, insert_params = cursor.calls[0]
    select_query, select_params = cursor.calls[1]
    assert "INSERT INTO operation_zone" in insert_query
    assert insert_params == (
        "caregiver_room",
        "map_test11_0423",
        "보호사실",
        "STAFF_STATION",
        True,
    )
    assert select_query == coordinate_config_repository.FIND_OPERATION_ZONE_SQL
    assert select_params == ("map_test11_0423", "caregiver_room")


def test_coordinate_config_repository_creates_patrol_area_in_transaction(
    monkeypatch,
):
    inserted_row = {
        "patrol_area_id": "patrol_day_01",
        "map_id": "map_test11_0423",
        "patrol_area_name": "주간 병동 순찰",
        "revision": 1,
    }
    cursor = FakeCursor(rows=[inserted_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )
    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 0.0},
        ],
    }

    row = coordinate_config_repository.CoordinateConfigRepository().create_patrol_area(
        map_id="map_test11_0423",
        patrol_area_id="patrol_day_01",
        patrol_area_name="주간 병동 순찰",
        path_json=path_json,
        is_enabled=True,
    )

    assert row == inserted_row
    assert connection.began is True
    assert connection.committed is True
    insert_query, insert_params = cursor.calls[0]
    select_query, select_params = cursor.calls[1]
    assert insert_query == coordinate_config_repository.INSERT_PATROL_AREA_SQL
    assert insert_params == (
        "patrol_day_01",
        "map_test11_0423",
        "주간 병동 순찰",
        '{"header":{"frame_id":"map"},"poses":[{"x":0.0,"y":0.0,"yaw":0.0},'
        '{"x":1.0,"y":1.0,"yaw":0.0}]}',
        True,
    )
    assert select_query == coordinate_config_repository.FIND_PATROL_AREA_SQL
    assert select_params == ("patrol_day_01",)


def test_coordinate_config_repository_updates_operation_zone_with_revision_lock(
    monkeypatch,
):
    locked_row = {"zone_id": "room_301", "map_id": "map_test11_0423", "revision": 1}
    updated_row = {
        "zone_id": "room_301",
        "map_id": "map_test11_0423",
        "revision": 2,
        "is_enabled": False,
    }
    cursor = FakeCursor(rows=[locked_row, updated_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )

    result = coordinate_config_repository.CoordinateConfigRepository().update_operation_zone(
        map_id="map_test11_0423",
        zone_id="room_301",
        expected_revision=1,
        zone_name="301호",
        zone_type="ROOM",
        is_enabled=False,
    )

    assert result == {"status": "UPDATED", "operation_zone": updated_row}
    assert connection.began is True
    assert connection.committed is True
    lock_query, lock_params = cursor.calls[0]
    update_query, update_params = cursor.calls[1]
    select_query, select_params = cursor.calls[2]
    assert lock_query == coordinate_config_repository.LOCK_OPERATION_ZONE_SQL
    assert lock_params == ("map_test11_0423", "room_301")
    assert "revision = revision + 1" in update_query
    assert update_params == ("301호", "ROOM", False, "map_test11_0423", "room_301")
    assert select_query == coordinate_config_repository.FIND_OPERATION_ZONE_SQL
    assert select_params == ("map_test11_0423", "room_301")


def test_coordinate_config_repository_reports_operation_zone_revision_conflict(
    monkeypatch,
):
    cursor = FakeCursor(
        rows=[{"zone_id": "room_301", "map_id": "map_test11_0423", "revision": 2}]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )

    result = coordinate_config_repository.CoordinateConfigRepository().update_operation_zone(
        map_id="map_test11_0423",
        zone_id="room_301",
        expected_revision=1,
        zone_name="301호",
        zone_type="ROOM",
        is_enabled=True,
    )

    assert result["status"] == "REVISION_CONFLICT"
    assert connection.committed is True
    assert len(cursor.calls) == 1


def test_coordinate_config_repository_updates_operation_zone_boundary_with_revision_lock(
    monkeypatch,
):
    locked_row = {"zone_id": "room_301", "map_id": "map_test11_0423", "revision": 2}
    updated_row = {
        "zone_id": "room_301",
        "map_id": "map_test11_0423",
        "revision": 3,
        "boundary_json": '{"type":"POLYGON"}',
    }
    cursor = FakeCursor(rows=[locked_row, updated_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )
    boundary_json = {
        "type": "POLYGON",
        "header": {"frame_id": "map"},
        "vertices": [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
            {"x": 1.0, "y": 1.0},
        ],
    }

    result = coordinate_config_repository.CoordinateConfigRepository().update_operation_zone_boundary(
        map_id="map_test11_0423",
        zone_id="room_301",
        expected_revision=2,
        boundary_json=boundary_json,
    )

    assert result == {"status": "UPDATED", "operation_zone": updated_row}
    assert connection.began is True
    assert connection.committed is True
    lock_query, lock_params = cursor.calls[0]
    update_query, update_params = cursor.calls[1]
    select_query, select_params = cursor.calls[2]
    assert lock_query == coordinate_config_repository.LOCK_OPERATION_ZONE_SQL
    assert lock_params == ("map_test11_0423", "room_301")
    assert update_query == coordinate_config_repository.UPDATE_OPERATION_ZONE_BOUNDARY_SQL
    assert update_params == (
        '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":0.0,"y":0.0},'
        '{"x":1.0,"y":0.0},{"x":1.0,"y":1.0}]}',
        "map_test11_0423",
        "room_301",
    )
    assert select_query == coordinate_config_repository.FIND_OPERATION_ZONE_SQL
    assert select_params == ("map_test11_0423", "room_301")


def test_coordinate_config_repository_clears_operation_zone_boundary(
    monkeypatch,
):
    locked_row = {"zone_id": "room_301", "map_id": "map_test11_0423", "revision": 2}
    updated_row = {
        "zone_id": "room_301",
        "map_id": "map_test11_0423",
        "revision": 3,
        "boundary_json": None,
    }
    cursor = FakeCursor(rows=[locked_row, updated_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )

    result = coordinate_config_repository.CoordinateConfigRepository().update_operation_zone_boundary(
        map_id="map_test11_0423",
        zone_id="room_301",
        expected_revision=2,
        boundary_json=None,
    )

    assert result == {"status": "UPDATED", "operation_zone": updated_row}
    assert cursor.calls[1] == (
        coordinate_config_repository.UPDATE_OPERATION_ZONE_BOUNDARY_SQL,
        (None, "map_test11_0423", "room_301"),
    )


def test_coordinate_config_repository_reports_boundary_revision_conflict(
    monkeypatch,
):
    cursor = FakeCursor(
        rows=[{"zone_id": "room_301", "map_id": "map_test11_0423", "revision": 3}]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )

    result = coordinate_config_repository.CoordinateConfigRepository().update_operation_zone_boundary(
        map_id="map_test11_0423",
        zone_id="room_301",
        expected_revision=2,
        boundary_json=None,
    )

    assert result["status"] == "REVISION_CONFLICT"
    assert connection.committed is True
    assert len(cursor.calls) == 1


def test_coordinate_config_repository_exposes_async_operation_zone_mutations(
    monkeypatch,
):
    calls = []
    rows = [
        {"zone_id": "caregiver_room", "map_id": "map_test11_0423"},
        {"zone_id": "room_301", "map_id": "map_test11_0423", "revision": 1},
        {"zone_id": "room_301", "map_id": "map_test11_0423", "revision": 2},
    ]

    class AsyncCursor:
        def __init__(self):
            self.rowcount = 0

        async def execute(self, query, params=None):
            calls.append((query, params))
            self.rowcount = 1

        async def fetchone(self):
            return rows.pop(0)

    @asynccontextmanager
    async def fake_async_transaction():
        yield AsyncCursor()

    monkeypatch.setattr(
        coordinate_config_repository,
        "async_transaction",
        fake_async_transaction,
    )

    async def scenario():
        repository = coordinate_config_repository.CoordinateConfigRepository()
        created = await repository.async_create_operation_zone(
            map_id="map_test11_0423",
            zone_id="caregiver_room",
            zone_name="보호사실",
            zone_type="STAFF_STATION",
            is_enabled=True,
        )
        updated = await repository.async_update_operation_zone(
            map_id="map_test11_0423",
            zone_id="room_301",
            expected_revision=1,
            zone_name="301호",
            zone_type="ROOM",
            is_enabled=False,
        )
        return created, updated

    created, updated = asyncio.run(scenario())

    assert created["zone_id"] == "caregiver_room"
    assert updated == {
        "status": "UPDATED",
        "operation_zone": {
            "zone_id": "room_301",
            "map_id": "map_test11_0423",
            "revision": 2,
        },
    }
    assert calls == [
        (
            coordinate_config_repository.INSERT_OPERATION_ZONE_SQL,
            (
                "caregiver_room",
                "map_test11_0423",
                "보호사실",
                "STAFF_STATION",
                True,
            ),
        ),
        (
            coordinate_config_repository.FIND_OPERATION_ZONE_SQL,
            ("map_test11_0423", "caregiver_room"),
        ),
        (
            coordinate_config_repository.LOCK_OPERATION_ZONE_SQL,
            ("map_test11_0423", "room_301"),
        ),
        (
            coordinate_config_repository.UPDATE_OPERATION_ZONE_SQL,
            ("301호", "ROOM", False, "map_test11_0423", "room_301"),
        ),
        (
            coordinate_config_repository.FIND_OPERATION_ZONE_SQL,
            ("map_test11_0423", "room_301"),
        ),
    ]


def test_coordinate_config_repository_exposes_async_operation_zone_boundary_update(
    monkeypatch,
):
    calls = []
    rows = [
        {"zone_id": "room_301", "map_id": "map_test11_0423", "revision": 2},
        {"zone_id": "room_301", "map_id": "map_test11_0423", "revision": 3},
    ]

    class AsyncCursor:
        async def execute(self, query, params=None):
            calls.append((query, params))

        async def fetchone(self):
            return rows.pop(0)

    @asynccontextmanager
    async def fake_async_transaction():
        yield AsyncCursor()

    monkeypatch.setattr(
        coordinate_config_repository,
        "async_transaction",
        fake_async_transaction,
    )

    async def scenario():
        return await coordinate_config_repository.CoordinateConfigRepository().async_update_operation_zone_boundary(
            map_id="map_test11_0423",
            zone_id="room_301",
            expected_revision=2,
            boundary_json={
                "type": "POLYGON",
                "header": {"frame_id": "map"},
                "vertices": [
                    {"x": 0.0, "y": 0.0},
                    {"x": 1.0, "y": 0.0},
                    {"x": 1.0, "y": 1.0},
                ],
            },
        )

    result = asyncio.run(scenario())

    assert result == {
        "status": "UPDATED",
        "operation_zone": {
            "zone_id": "room_301",
            "map_id": "map_test11_0423",
            "revision": 3,
        },
    }
    assert calls == [
        (
            coordinate_config_repository.LOCK_OPERATION_ZONE_SQL,
            ("map_test11_0423", "room_301"),
        ),
        (
            coordinate_config_repository.UPDATE_OPERATION_ZONE_BOUNDARY_SQL,
            (
                '{"type":"POLYGON","header":{"frame_id":"map"},"vertices":[{"x":0.0,"y":0.0},'
                '{"x":1.0,"y":0.0},{"x":1.0,"y":1.0}]}',
                "map_test11_0423",
                "room_301",
            ),
        ),
        (
            coordinate_config_repository.FIND_OPERATION_ZONE_SQL,
            ("map_test11_0423", "room_301"),
        ),
    ]


def test_coordinate_config_repository_updates_goal_pose_with_stale_check(
    monkeypatch,
):
    locked_row = {
        "goal_pose_id": "delivery_room_301",
        "map_id": "map_test11_0423",
        "updated_at": "2026-05-02T12:01:00",
    }
    updated_row = {
        "goal_pose_id": "delivery_room_301",
        "map_id": "map_test11_0423",
        "zone_id": "room_301",
        "purpose": "DESTINATION",
    }
    cursor = FakeCursor(rows=[locked_row, updated_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )

    result = coordinate_config_repository.CoordinateConfigRepository().update_goal_pose(
        map_id="map_test11_0423",
        goal_pose_id="delivery_room_301",
        expected_updated_at="2026-05-02T12:01:00",
        zone_id="room_301",
        purpose="DESTINATION",
        pose_x=1.7,
        pose_y=0.02,
        pose_yaw=0.0,
        frame_id="map",
        is_enabled=True,
    )

    assert result == {"status": "UPDATED", "goal_pose": updated_row}
    assert connection.began is True
    assert connection.committed is True
    lock_query, lock_params = cursor.calls[0]
    update_query, update_params = cursor.calls[1]
    select_query, select_params = cursor.calls[2]
    assert lock_query == coordinate_config_repository.LOCK_GOAL_POSE_SQL
    assert lock_params == ("delivery_room_301", "map_test11_0423")
    assert "UPDATE goal_pose" in update_query
    assert update_params == (
        "room_301",
        "DESTINATION",
        1.7,
        0.02,
        0.0,
        "map",
        True,
        "delivery_room_301",
        "map_test11_0423",
    )
    assert select_query == coordinate_config_repository.FIND_GOAL_POSE_SQL
    assert select_params == ("delivery_room_301",)


def test_coordinate_config_repository_reports_goal_pose_stale_conflict(
    monkeypatch,
):
    cursor = FakeCursor(
        rows=[
            {
                "goal_pose_id": "delivery_room_301",
                "map_id": "map_test11_0423",
                "updated_at": "2026-05-02T12:02:00",
            }
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )

    result = coordinate_config_repository.CoordinateConfigRepository().update_goal_pose(
        map_id="map_test11_0423",
        goal_pose_id="delivery_room_301",
        expected_updated_at="2026-05-02T12:01:00",
        zone_id="room_301",
        purpose="DESTINATION",
        pose_x=1.7,
        pose_y=0.02,
        pose_yaw=0.0,
        frame_id="map",
        is_enabled=True,
    )

    assert result["status"] == "STALE"
    assert connection.committed is True
    assert len(cursor.calls) == 1


def test_coordinate_config_repository_exposes_async_goal_pose_update(monkeypatch):
    calls = []
    rows = [
        {
            "goal_pose_id": "delivery_room_301",
            "map_id": "map_test11_0423",
            "updated_at": "2026-05-02T12:01:00",
        },
        {
            "goal_pose_id": "delivery_room_301",
            "map_id": "map_test11_0423",
            "purpose": "DESTINATION",
        },
    ]

    class AsyncCursor:
        async def execute(self, query, params=None):
            calls.append((query, params))

        async def fetchone(self):
            return rows.pop(0)

    @asynccontextmanager
    async def fake_async_transaction():
        yield AsyncCursor()

    monkeypatch.setattr(
        coordinate_config_repository,
        "async_transaction",
        fake_async_transaction,
    )

    async def scenario():
        return await coordinate_config_repository.CoordinateConfigRepository().async_update_goal_pose(
            map_id="map_test11_0423",
            goal_pose_id="delivery_room_301",
            expected_updated_at=None,
            zone_id=None,
            purpose="DESTINATION",
            pose_x=1.7,
            pose_y=0.02,
            pose_yaw=0.0,
            frame_id="map",
            is_enabled=False,
        )

    result = asyncio.run(scenario())

    assert result == {
        "status": "UPDATED",
        "goal_pose": {
            "goal_pose_id": "delivery_room_301",
            "map_id": "map_test11_0423",
            "purpose": "DESTINATION",
        },
    }
    assert calls == [
        (
            coordinate_config_repository.LOCK_GOAL_POSE_SQL,
            ("delivery_room_301", "map_test11_0423"),
        ),
        (
            coordinate_config_repository.UPDATE_GOAL_POSE_SQL,
            (
                None,
                "DESTINATION",
                1.7,
                0.02,
                0.0,
                "map",
                False,
                "delivery_room_301",
                "map_test11_0423",
            ),
        ),
        (
            coordinate_config_repository.FIND_GOAL_POSE_SQL,
            ("delivery_room_301",),
        ),
    ]


def test_coordinate_config_repository_updates_patrol_area_path_with_revision_lock(
    monkeypatch,
):
    locked_row = {
        "patrol_area_id": "patrol_ward_night_01",
        "map_id": "map_test11_0423",
        "revision": 7,
    }
    updated_row = {
        "patrol_area_id": "patrol_ward_night_01",
        "map_id": "map_test11_0423",
        "revision": 8,
    }
    cursor = FakeCursor(rows=[locked_row, updated_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )
    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 0.0},
        ],
    }

    result = coordinate_config_repository.CoordinateConfigRepository().update_patrol_area_path(
        map_id="map_test11_0423",
        patrol_area_id="patrol_ward_night_01",
        expected_revision=7,
        path_json=path_json,
    )

    assert result == {"status": "UPDATED", "patrol_area": updated_row}
    assert connection.began is True
    assert connection.committed is True
    lock_query, lock_params = cursor.calls[0]
    update_query, update_params = cursor.calls[1]
    select_query, select_params = cursor.calls[2]
    assert lock_query == coordinate_config_repository.LOCK_PATROL_AREA_SQL
    assert lock_params == ("patrol_ward_night_01", "map_test11_0423")
    assert "revision = revision + 1" in update_query
    assert update_params[1:] == ("patrol_ward_night_01", "map_test11_0423")
    assert update_params[0] == (
        '{"header":{"frame_id":"map"},"poses":[{"x":0.0,"y":0.0,"yaw":0.0},'
        '{"x":1.0,"y":1.0,"yaw":0.0}]}'
    )
    assert select_query == coordinate_config_repository.FIND_PATROL_AREA_SQL
    assert select_params == ("patrol_ward_night_01",)


def test_coordinate_config_repository_updates_patrol_area_row_with_revision_lock(
    monkeypatch,
):
    locked_row = {
        "patrol_area_id": "patrol_ward_night_01",
        "map_id": "map_test11_0423",
        "revision": 7,
    }
    updated_row = {
        "patrol_area_id": "patrol_ward_night_01",
        "map_id": "map_test11_0423",
        "revision": 8,
        "is_enabled": False,
    }
    cursor = FakeCursor(rows=[locked_row, updated_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )
    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 0.0},
        ],
    }

    result = coordinate_config_repository.CoordinateConfigRepository().update_patrol_area(
        map_id="map_test11_0423",
        patrol_area_id="patrol_ward_night_01",
        expected_revision=7,
        patrol_area_name="야간 병동 순찰",
        path_json=path_json,
        is_enabled=False,
    )

    assert result == {"status": "UPDATED", "patrol_area": updated_row}
    assert connection.began is True
    assert connection.committed is True
    lock_query, lock_params = cursor.calls[0]
    update_query, update_params = cursor.calls[1]
    select_query, select_params = cursor.calls[2]
    assert lock_query == coordinate_config_repository.LOCK_PATROL_AREA_SQL
    assert lock_params == ("patrol_ward_night_01", "map_test11_0423")
    assert update_query == coordinate_config_repository.UPDATE_PATROL_AREA_SQL
    assert update_params == (
        "야간 병동 순찰",
        '{"header":{"frame_id":"map"},"poses":[{"x":0.0,"y":0.0,"yaw":0.0},'
        '{"x":1.0,"y":1.0,"yaw":0.0}]}',
        False,
        "patrol_ward_night_01",
        "map_test11_0423",
    )
    assert select_query == coordinate_config_repository.FIND_PATROL_AREA_SQL
    assert select_params == ("patrol_ward_night_01",)


def test_coordinate_config_repository_reports_patrol_area_revision_conflict(
    monkeypatch,
):
    cursor = FakeCursor(
        rows=[
            {
                "patrol_area_id": "patrol_ward_night_01",
                "map_id": "map_test11_0423",
                "revision": 8,
            }
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(
        coordinate_config_repository,
        "get_connection",
        lambda: connection,
    )

    result = coordinate_config_repository.CoordinateConfigRepository().update_patrol_area_path(
        map_id="map_test11_0423",
        patrol_area_id="patrol_ward_night_01",
        expected_revision=7,
        path_json={"header": {"frame_id": "map"}, "poses": []},
    )

    assert result["status"] == "REVISION_CONFLICT"
    assert connection.committed is True
    assert len(cursor.calls) == 1


def test_coordinate_config_repository_exposes_async_patrol_area_path_update(
    monkeypatch,
):
    calls = []
    rows = [
        {
            "patrol_area_id": "patrol_ward_night_01",
            "map_id": "map_test11_0423",
            "revision": 7,
        },
        {
            "patrol_area_id": "patrol_ward_night_01",
            "map_id": "map_test11_0423",
            "revision": 8,
        },
    ]

    class AsyncCursor:
        async def execute(self, query, params=None):
            calls.append((query, params))

        async def fetchone(self):
            return rows.pop(0)

    @asynccontextmanager
    async def fake_async_transaction():
        yield AsyncCursor()

    monkeypatch.setattr(
        coordinate_config_repository,
        "async_transaction",
        fake_async_transaction,
    )

    async def scenario():
        return await coordinate_config_repository.CoordinateConfigRepository().async_update_patrol_area_path(
            map_id="map_test11_0423",
            patrol_area_id="patrol_ward_night_01",
            expected_revision=7,
            path_json={
                "header": {"frame_id": "map"},
                "poses": [
                    {"x": 0.0, "y": 0.0, "yaw": 0.0},
                    {"x": 1.0, "y": 1.0, "yaw": 0.0},
                ],
            },
        )

    result = asyncio.run(scenario())

    assert result == {
        "status": "UPDATED",
        "patrol_area": {
            "patrol_area_id": "patrol_ward_night_01",
            "map_id": "map_test11_0423",
            "revision": 8,
        },
    }
    assert calls == [
        (
            coordinate_config_repository.LOCK_PATROL_AREA_SQL,
            ("patrol_ward_night_01", "map_test11_0423"),
        ),
        (
            coordinate_config_repository.UPDATE_PATROL_AREA_PATH_SQL,
            (
                '{"header":{"frame_id":"map"},"poses":[{"x":0.0,"y":0.0,"yaw":0.0},'
                '{"x":1.0,"y":1.0,"yaw":0.0}]}',
                "patrol_ward_night_01",
                "map_test11_0423",
            ),
        ),
        (
            coordinate_config_repository.FIND_PATROL_AREA_SQL,
            ("patrol_ward_night_01",),
        ),
    ]
