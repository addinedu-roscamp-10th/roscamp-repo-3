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

    def fetchall(self):
        if not self.rows:
            return []
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
        if query == fms_config_repository.LIST_ROUTES_SQL:
            return [{"route_id": "route_corridor_01_02"}]
        if query == fms_config_repository.LIST_ROUTE_WAYPOINTS_FOR_MAP_SQL:
            return [
                {
                    "route_id": "route_corridor_01_02",
                    "sequence_no": 1,
                    "waypoint_id": "corridor_01",
                }
            ]
        return [{"waypoint_id": "corridor_01"}]

    monkeypatch.setattr(fms_config_repository, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(fms_config_repository, "fetch_all", fake_fetch_all)

    repository = fms_config_repository.FmsConfigRepository()

    assert repository.get_active_map_profile() == {"map_id": "map_0504"}
    assert repository.get_waypoints(
        map_id="map_0504",
        include_disabled=False,
    ) == [{"waypoint_id": "corridor_01"}]
    assert repository.get_edges(
        map_id="map_0504",
        include_disabled=True,
    ) == [{"waypoint_id": "corridor_01"}]
    assert repository.get_routes(
        map_id="map_0504",
        include_disabled=False,
    ) == [
        {
            "route_id": "route_corridor_01_02",
            "waypoint_sequence": [
                {
                    "route_id": "route_corridor_01_02",
                    "sequence_no": 1,
                    "waypoint_id": "corridor_01",
                }
            ],
        }
    ]

    assert calls == [
        ("one", fms_config_repository.ACTIVE_MAP_PROFILE_SQL, None),
        (
            "all",
            fms_config_repository.LIST_WAYPOINTS_SQL,
            ("map_0504", False),
        ),
        (
            "all",
            fms_config_repository.LIST_EDGES_SQL,
            ("map_0504", True),
        ),
        (
            "all",
            fms_config_repository.LIST_ROUTES_SQL,
            ("map_0504", False),
        ),
        (
            "all",
            fms_config_repository.LIST_ROUTE_WAYPOINTS_FOR_MAP_SQL,
            ("map_0504", False),
        ),
    ]
    assert "FROM fms_waypoint" in fms_config_repository.LIST_WAYPOINTS_SQL
    assert "FROM fms_edge" in fms_config_repository.LIST_EDGES_SQL
    assert "FROM fms_route" in fms_config_repository.LIST_ROUTES_SQL


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


def test_fms_config_repository_inserts_missing_edge(monkeypatch):
    inserted_row = {
        "edge_id": "edge_corridor_01_02",
        "map_id": "map_0504",
    }
    cursor = FakeCursor(rows=[None, inserted_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(fms_config_repository, "get_connection", lambda: connection)

    result = fms_config_repository.FmsConfigRepository().upsert_edge(
        map_id="map_0504",
        edge_id="edge_corridor_01_02",
        expected_updated_at=None,
        from_waypoint_id="corridor_01",
        to_waypoint_id="corridor_02",
        is_bidirectional=True,
        traversal_cost=1.5,
        priority=10,
        is_enabled=True,
    )

    assert result == {"status": "UPSERTED", "edge": inserted_row}
    assert connection.began is True
    assert connection.committed is True
    lock_query, lock_params = cursor.calls[0]
    insert_query, insert_params = cursor.calls[1]
    select_query, select_params = cursor.calls[2]
    assert lock_query == fms_config_repository.LOCK_EDGE_SQL
    assert lock_params == ("edge_corridor_01_02",)
    assert "INSERT INTO fms_edge" in insert_query
    assert insert_params == (
        "edge_corridor_01_02",
        "map_0504",
        "corridor_01",
        "corridor_02",
        True,
        1.5,
        10,
        True,
    )
    assert select_query == fms_config_repository.FIND_EDGE_SQL
    assert select_params == ("edge_corridor_01_02",)


def test_fms_config_repository_updates_existing_edge_with_stale_check(monkeypatch):
    locked_row = {
        "edge_id": "edge_corridor_01_02",
        "map_id": "map_0504",
        "updated_at": "2026-05-04T10:04:00",
    }
    updated_row = {
        "edge_id": "edge_corridor_01_02",
        "map_id": "map_0504",
    }
    cursor = FakeCursor(rows=[locked_row, updated_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(fms_config_repository, "get_connection", lambda: connection)

    result = fms_config_repository.FmsConfigRepository().upsert_edge(
        map_id="map_0504",
        edge_id="edge_corridor_01_02",
        expected_updated_at="2026-05-04T10:04:00",
        from_waypoint_id="corridor_01",
        to_waypoint_id="corridor_02",
        is_bidirectional=False,
        traversal_cost=None,
        priority=None,
        is_enabled=False,
    )

    assert result == {"status": "UPSERTED", "edge": updated_row}
    update_query, update_params = cursor.calls[1]
    assert "UPDATE fms_edge" in update_query
    assert update_params == (
        "corridor_01",
        "corridor_02",
        False,
        None,
        None,
        False,
        "edge_corridor_01_02",
        "map_0504",
    )


def test_fms_config_repository_reports_edge_stale_conflict(monkeypatch):
    locked_row = {
        "edge_id": "edge_corridor_01_02",
        "map_id": "map_0504",
        "updated_at": "2026-05-04T10:04:00",
    }
    cursor = FakeCursor(rows=[locked_row])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(fms_config_repository, "get_connection", lambda: connection)

    result = fms_config_repository.FmsConfigRepository().upsert_edge(
        map_id="map_0504",
        edge_id="edge_corridor_01_02",
        expected_updated_at="2026-05-04T10:00:00",
        from_waypoint_id="corridor_01",
        to_waypoint_id="corridor_02",
        is_bidirectional=True,
        traversal_cost=1.5,
        priority=10,
        is_enabled=True,
    )

    assert result == {"status": "STALE", "edge": locked_row}
    assert len(cursor.calls) == 1


def test_fms_config_repository_inserts_missing_route(monkeypatch):
    inserted_row = {
        "route_id": "route_corridor_01_02",
        "map_id": "map_0504",
        "revision": 1,
    }
    sequence_rows = [
        {"sequence_no": 1, "waypoint_id": "corridor_01"},
        {"sequence_no": 2, "waypoint_id": "corridor_02"},
    ]
    cursor = FakeCursor(rows=[None, inserted_row, sequence_rows])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(fms_config_repository, "get_connection", lambda: connection)

    result = fms_config_repository.FmsConfigRepository().upsert_route(
        map_id="map_0504",
        route_id="route_corridor_01_02",
        expected_revision=None,
        route_name="복도 1-2",
        route_scope="COMMON",
        waypoint_sequence=[
            {
                "sequence_no": 1,
                "waypoint_id": "corridor_01",
                "yaw_policy": "AUTO_NEXT",
                "fixed_pose_yaw": None,
                "stop_required": True,
                "dwell_sec": None,
            },
            {
                "sequence_no": 2,
                "waypoint_id": "corridor_02",
                "yaw_policy": "FIXED",
                "fixed_pose_yaw": 0.0,
                "stop_required": False,
                "dwell_sec": 1.5,
            },
        ],
        is_enabled=True,
    )

    assert result == {
        "status": "UPSERTED",
        "route": {**inserted_row, "waypoint_sequence": sequence_rows},
    }
    assert connection.began is True
    assert connection.committed is True
    assert cursor.calls[0] == (
        fms_config_repository.LOCK_ROUTE_SQL,
        ("route_corridor_01_02",),
    )
    assert "INSERT INTO fms_route" in cursor.calls[1][0]
    assert cursor.calls[1][1] == (
        "route_corridor_01_02",
        "map_0504",
        "복도 1-2",
        "COMMON",
        True,
    )
    assert "INSERT INTO fms_route_waypoint" in cursor.calls[2][0]
    assert cursor.calls[2][1] == (
        "route_corridor_01_02",
        1,
        "corridor_01",
        "AUTO_NEXT",
        None,
        True,
        None,
    )
    assert cursor.calls[4] == (
        fms_config_repository.FIND_ROUTE_SQL,
        ("route_corridor_01_02",),
    )
    assert cursor.calls[5] == (
        fms_config_repository.LIST_ROUTE_WAYPOINTS_SQL,
        ("route_corridor_01_02",),
    )


def test_fms_config_repository_updates_existing_route_with_revision_check(monkeypatch):
    locked_row = {
        "route_id": "route_corridor_01_02",
        "map_id": "map_0504",
        "revision": 1,
    }
    updated_row = {
        "route_id": "route_corridor_01_02",
        "map_id": "map_0504",
        "revision": 2,
    }
    sequence_rows = [
        {"sequence_no": 1, "waypoint_id": "corridor_02"},
        {"sequence_no": 2, "waypoint_id": "corridor_01"},
    ]
    cursor = FakeCursor(rows=[locked_row, updated_row, sequence_rows])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(fms_config_repository, "get_connection", lambda: connection)

    result = fms_config_repository.FmsConfigRepository().upsert_route(
        map_id="map_0504",
        route_id="route_corridor_01_02",
        expected_revision=1,
        route_name="복도 2-1",
        route_scope="PATROL",
        waypoint_sequence=[
            {"sequence_no": 1, "waypoint_id": "corridor_02", "yaw_policy": "AUTO_NEXT"},
            {"sequence_no": 2, "waypoint_id": "corridor_01", "yaw_policy": "AUTO_NEXT"},
        ],
        is_enabled=False,
    )

    assert result == {
        "status": "UPSERTED",
        "route": {**updated_row, "waypoint_sequence": sequence_rows},
    }
    assert "UPDATE fms_route" in cursor.calls[1][0]
    assert cursor.calls[1][1] == (
        "복도 2-1",
        "PATROL",
        False,
        "route_corridor_01_02",
        "map_0504",
    )
    assert cursor.calls[2] == (
        fms_config_repository.DELETE_ROUTE_WAYPOINTS_SQL,
        ("route_corridor_01_02",),
    )


def test_fms_config_repository_reports_route_stale_conflict(monkeypatch):
    locked_row = {
        "route_id": "route_corridor_01_02",
        "map_id": "map_0504",
        "revision": 2,
    }
    sequence_rows = [{"sequence_no": 1, "waypoint_id": "corridor_01"}]
    cursor = FakeCursor(rows=[locked_row, sequence_rows])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(fms_config_repository, "get_connection", lambda: connection)

    result = fms_config_repository.FmsConfigRepository().upsert_route(
        map_id="map_0504",
        route_id="route_corridor_01_02",
        expected_revision=1,
        route_name="복도 1-2",
        route_scope="COMMON",
        waypoint_sequence=[
            {"sequence_no": 1, "waypoint_id": "corridor_01", "yaw_policy": "AUTO_NEXT"},
            {"sequence_no": 2, "waypoint_id": "corridor_02", "yaw_policy": "AUTO_NEXT"},
        ],
        is_enabled=True,
    )

    assert result == {
        "status": "STALE",
        "route": {**locked_row, "waypoint_sequence": sequence_rows},
    }
    assert cursor.calls == [
        (fms_config_repository.LOCK_ROUTE_SQL, ("route_corridor_01_02",)),
        (
            fms_config_repository.LIST_ROUTE_WAYPOINTS_SQL,
            ("route_corridor_01_02",),
        ),
    ]


def test_fms_config_repository_exposes_async_methods(monkeypatch):
    calls = []

    async def fake_async_fetch_one(query, params=None):
        calls.append(("one", query, params))
        return {"map_id": "map_0504"}

    async def fake_async_fetch_all(query, params=None):
        calls.append(("all", query, params))
        if query == fms_config_repository.LIST_ROUTES_SQL:
            return [{"route_id": "route_corridor_01_02"}]
        if query == fms_config_repository.LIST_ROUTE_WAYPOINTS_FOR_MAP_SQL:
            return [
                {
                    "route_id": "route_corridor_01_02",
                    "sequence_no": 1,
                    "waypoint_id": "corridor_01",
                }
            ]
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
        edges = await repository.async_get_edges(
            map_id="map_0504",
            include_disabled=False,
        )
        routes = await repository.async_get_routes(
            map_id="map_0504",
            include_disabled=True,
        )
        return active_map, waypoints, edges, routes

    active_map, waypoints, edges, routes = asyncio.run(scenario())

    assert active_map == {"map_id": "map_0504"}
    assert waypoints == [{"waypoint_id": "corridor_01"}]
    assert edges == [{"waypoint_id": "corridor_01"}]
    assert routes == [
        {
            "route_id": "route_corridor_01_02",
            "waypoint_sequence": [
                {
                    "route_id": "route_corridor_01_02",
                    "sequence_no": 1,
                    "waypoint_id": "corridor_01",
                }
            ],
        }
    ]
    assert calls == [
        ("one", fms_config_repository.ACTIVE_MAP_PROFILE_SQL, None),
        ("all", fms_config_repository.LIST_WAYPOINTS_SQL, ("map_0504", True)),
        ("all", fms_config_repository.LIST_EDGES_SQL, ("map_0504", False)),
        ("all", fms_config_repository.LIST_ROUTES_SQL, ("map_0504", True)),
        (
            "all",
            fms_config_repository.LIST_ROUTE_WAYPOINTS_FOR_MAP_SQL,
            ("map_0504", True),
        ),
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


def test_fms_config_repository_async_upsert_edge(monkeypatch):
    locked_row = None
    inserted_row = {
        "edge_id": "edge_corridor_01_02",
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
        return await fms_config_repository.FmsConfigRepository().async_upsert_edge(
            map_id="map_0504",
            edge_id="edge_corridor_01_02",
            expected_updated_at=None,
            from_waypoint_id="corridor_01",
            to_waypoint_id="corridor_02",
            is_bidirectional=True,
            traversal_cost=1.5,
            priority=10,
            is_enabled=True,
        )

    result = asyncio.run(scenario())

    assert result == {"status": "UPSERTED", "edge": inserted_row}
    assert calls[0] == (
        fms_config_repository.LOCK_EDGE_SQL,
        ("edge_corridor_01_02",),
    )
    assert "INSERT INTO fms_edge" in calls[1][0]
    assert calls[2] == (fms_config_repository.FIND_EDGE_SQL, ("edge_corridor_01_02",))


def test_fms_config_repository_async_upsert_route(monkeypatch):
    locked_row = None
    inserted_row = {
        "route_id": "route_corridor_01_02",
        "map_id": "map_0504",
        "revision": 1,
    }
    sequence_rows = [
        {"sequence_no": 1, "waypoint_id": "corridor_01"},
        {"sequence_no": 2, "waypoint_id": "corridor_02"},
    ]
    calls = []

    class AsyncCursor:
        def __init__(self):
            self.rows = [locked_row, inserted_row, sequence_rows]

        async def execute(self, query, params=None):
            calls.append((query, params))

        async def fetchone(self):
            if not self.rows:
                return None
            return self.rows.pop(0)

        async def fetchall(self):
            if not self.rows:
                return []
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
        return await fms_config_repository.FmsConfigRepository().async_upsert_route(
            map_id="map_0504",
            route_id="route_corridor_01_02",
            expected_revision=None,
            route_name="복도 1-2",
            route_scope="COMMON",
            waypoint_sequence=[
                {
                    "sequence_no": 1,
                    "waypoint_id": "corridor_01",
                    "yaw_policy": "AUTO_NEXT",
                    "fixed_pose_yaw": None,
                    "stop_required": True,
                    "dwell_sec": None,
                },
                {
                    "sequence_no": 2,
                    "waypoint_id": "corridor_02",
                    "yaw_policy": "AUTO_NEXT",
                    "fixed_pose_yaw": None,
                    "stop_required": True,
                    "dwell_sec": None,
                },
            ],
            is_enabled=True,
        )

    result = asyncio.run(scenario())

    assert result == {
        "status": "UPSERTED",
        "route": {**inserted_row, "waypoint_sequence": sequence_rows},
    }
    assert calls[0] == (
        fms_config_repository.LOCK_ROUTE_SQL,
        ("route_corridor_01_02",),
    )
    assert "INSERT INTO fms_route" in calls[1][0]
    assert "INSERT INTO fms_route_waypoint" in calls[2][0]
    assert calls[-2] == (
        fms_config_repository.FIND_ROUTE_SQL,
        ("route_corridor_01_02",),
    )
    assert calls[-1] == (
        fms_config_repository.LIST_ROUTE_WAYPOINTS_SQL,
        ("route_corridor_01_02",),
    )
