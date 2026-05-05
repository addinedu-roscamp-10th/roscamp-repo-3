import asyncio
from datetime import datetime, timezone

from server.ropi_main_service.application.fms_config import FmsConfigService


class FakeFmsConfigRepository:
    def __init__(self):
        self.calls = []
        self.map_profile = {
            "map_id": "map_0504",
            "map_name": "map_0504",
            "map_revision": "2",
            "yaml_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_0504.yaml",
            "pgm_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_0504.pgm",
            "frame_id": "map",
            "is_active": 1,
        }
        self.waypoints = [
            {
                "waypoint_id": "corridor_01",
                "map_id": "map_0504",
                "display_name": "복도1",
                "waypoint_type": "CORRIDOR",
                "pose_x": "0.12",
                "pose_y": "-0.34",
                "pose_yaw": "1.57",
                "frame_id": "map",
                "snap_group": "main_corridor",
                "is_enabled": 1,
                "created_at": datetime(2026, 5, 4, 10, 0, 0),
                "updated_at": datetime(2026, 5, 4, 10, 1, 0),
            },
            {
                "waypoint_id": "corridor_02",
                "map_id": "map_0504",
                "display_name": "복도2",
                "waypoint_type": "CORRIDOR",
                "pose_x": "0.42",
                "pose_y": "-0.52",
                "pose_yaw": "0.0",
                "frame_id": "map",
                "snap_group": "main_corridor",
                "is_enabled": 1,
                "created_at": datetime(2026, 5, 4, 10, 0, 0),
                "updated_at": datetime(2026, 5, 4, 10, 1, 0),
            },
        ]
        self.edges = [
            {
                "edge_id": "edge_corridor_01_02",
                "map_id": "map_0504",
                "from_waypoint_id": "corridor_01",
                "to_waypoint_id": "corridor_02",
                "is_bidirectional": 1,
                "traversal_cost": "1.5",
                "priority": "10",
                "is_enabled": 1,
                "created_at": datetime(2026, 5, 4, 10, 3, 0),
                "updated_at": datetime(2026, 5, 4, 10, 4, 0),
            }
        ]
        self.upsert_result = None
        self.edge_upsert_result = None

    def get_active_map_profile(self):
        self.calls.append(("get_active_map_profile",))
        return self.map_profile

    async def async_get_active_map_profile(self):
        self.calls.append(("async_get_active_map_profile",))
        return self.map_profile

    def get_waypoints(self, *, map_id, include_disabled=True):
        self.calls.append(("get_waypoints", map_id, include_disabled))
        return self.waypoints

    async def async_get_waypoints(self, *, map_id, include_disabled=True):
        self.calls.append(("async_get_waypoints", map_id, include_disabled))
        return self.waypoints

    def get_edges(self, *, map_id, include_disabled=True):
        self.calls.append(("get_edges", map_id, include_disabled))
        return self.edges

    async def async_get_edges(self, *, map_id, include_disabled=True):
        self.calls.append(("async_get_edges", map_id, include_disabled))
        return self.edges

    def upsert_waypoint(self, *, map_id, **kwargs):
        self.calls.append(
            (
                "upsert_waypoint",
                map_id,
                kwargs["waypoint_id"],
                kwargs["expected_updated_at"],
                kwargs["display_name"],
                kwargs["waypoint_type"],
                kwargs["pose_x"],
                kwargs["pose_y"],
                kwargs["pose_yaw"],
                kwargs["frame_id"],
                kwargs["snap_group"],
                kwargs["is_enabled"],
            )
        )
        return self.upsert_result or {
            "status": "UPSERTED",
            "waypoint": {
                **self.waypoints[0],
                **kwargs,
                "map_id": map_id,
                "created_at": datetime(2026, 5, 4, 10, 0, 0),
                "updated_at": datetime(2026, 5, 4, 10, 2, 0),
            },
        }

    async def async_upsert_waypoint(self, *, map_id, **kwargs):
        self.calls.append(
            (
                "async_upsert_waypoint",
                map_id,
                kwargs["waypoint_id"],
                kwargs["expected_updated_at"],
            )
        )
        return self.upsert_result or {
            "status": "UPSERTED",
            "waypoint": {
                **self.waypoints[0],
                **kwargs,
                "map_id": map_id,
                "created_at": datetime(2026, 5, 4, 10, 0, 0),
                "updated_at": datetime(2026, 5, 4, 10, 2, 0),
            },
        }

    def upsert_edge(self, *, map_id, **kwargs):
        self.calls.append(
            (
                "upsert_edge",
                map_id,
                kwargs["edge_id"],
                kwargs["expected_updated_at"],
                kwargs["from_waypoint_id"],
                kwargs["to_waypoint_id"],
                kwargs["is_bidirectional"],
                kwargs["traversal_cost"],
                kwargs["priority"],
                kwargs["is_enabled"],
            )
        )
        return self.edge_upsert_result or {
            "status": "UPSERTED",
            "edge": {
                **self.edges[0],
                **kwargs,
                "map_id": map_id,
                "created_at": datetime(2026, 5, 4, 10, 3, 0),
                "updated_at": datetime(2026, 5, 4, 10, 5, 0),
            },
        }

    async def async_upsert_edge(self, *, map_id, **kwargs):
        self.calls.append(
            (
                "async_upsert_edge",
                map_id,
                kwargs["edge_id"],
                kwargs["expected_updated_at"],
            )
        )
        return self.edge_upsert_result or {
            "status": "UPSERTED",
            "edge": {
                **self.edges[0],
                **kwargs,
                "map_id": map_id,
                "created_at": datetime(2026, 5, 4, 10, 3, 0),
                "updated_at": datetime(2026, 5, 4, 10, 5, 0),
            },
        }


def _service(repository):
    return FmsConfigService(
        repository=repository,
        clock=lambda: datetime(2026, 5, 4, 1, 2, 3, tzinfo=timezone.utc),
    )


def test_fms_graph_bundle_formats_active_waypoint_foundation():
    repository = FakeFmsConfigRepository()

    response = _service(repository).get_active_graph_bundle(
        include_disabled=False,
        include_edges=True,
        include_routes=True,
        include_reservations=True,
    )

    assert response["result_code"] == "OK"
    assert response["result_message"] is None
    assert response["reason_code"] is None
    assert response["generated_at"] == "2026-05-04T01:02:03+00:00"
    assert response["map_profile"]["map_id"] == "map_0504"
    assert response["waypoints"] == [
        {
            "waypoint_id": "corridor_01",
            "map_id": "map_0504",
            "display_name": "복도1",
            "waypoint_type": "CORRIDOR",
            "pose_x": 0.12,
            "pose_y": -0.34,
            "pose_yaw": 1.57,
            "frame_id": "map",
            "snap_group": "main_corridor",
            "is_enabled": True,
            "created_at": "2026-05-04T10:00:00",
            "updated_at": "2026-05-04T10:01:00",
        },
        {
            "waypoint_id": "corridor_02",
            "map_id": "map_0504",
            "display_name": "복도2",
            "waypoint_type": "CORRIDOR",
            "pose_x": 0.42,
            "pose_y": -0.52,
            "pose_yaw": 0.0,
            "frame_id": "map",
            "snap_group": "main_corridor",
            "is_enabled": True,
            "created_at": "2026-05-04T10:00:00",
            "updated_at": "2026-05-04T10:01:00",
        },
    ]
    assert response["edges"] == [
        {
            "edge_id": "edge_corridor_01_02",
            "map_id": "map_0504",
            "from_waypoint_id": "corridor_01",
            "to_waypoint_id": "corridor_02",
            "is_bidirectional": True,
            "traversal_cost": 1.5,
            "priority": 10,
            "is_enabled": True,
            "created_at": "2026-05-04T10:03:00",
            "updated_at": "2026-05-04T10:04:00",
        }
    ]
    assert response["routes"] == []
    assert response["reservations"] == []
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_waypoints", "map_0504", False),
        ("get_edges", "map_0504", False),
    ]


def test_fms_graph_bundle_returns_not_found_without_active_map():
    repository = FakeFmsConfigRepository()
    repository.map_profile = None

    response = _service(repository).get_active_graph_bundle()

    assert response == {
        "result_code": "NOT_FOUND",
        "result_message": "active map이 설정되어 있지 않습니다.",
        "reason_code": "ACTIVE_MAP_NOT_FOUND",
        "generated_at": "2026-05-04T01:02:03+00:00",
        "map_profile": None,
        "waypoints": [],
        "edges": [],
        "routes": [],
        "reservations": [],
    }


def test_fms_upsert_waypoint_creates_or_updates_active_map_waypoint():
    repository = FakeFmsConfigRepository()

    response = _service(repository).upsert_waypoint(
        waypoint_id="corridor_02",
        expected_updated_at=None,
        display_name="복도2",
        waypoint_type="corridor",
        pose_x="0.42",
        pose_y="-0.52",
        pose_yaw="0.0",
        frame_id="map",
        snap_group="main_corridor",
        is_enabled=True,
    )

    assert response["result_code"] == "OK"
    assert response["reason_code"] is None
    assert response["waypoint"] == {
        "waypoint_id": "corridor_02",
        "map_id": "map_0504",
        "display_name": "복도2",
        "waypoint_type": "CORRIDOR",
        "pose_x": 0.42,
        "pose_y": -0.52,
        "pose_yaw": 0.0,
        "frame_id": "map",
        "snap_group": "main_corridor",
        "is_enabled": True,
        "created_at": "2026-05-04T10:00:00",
        "updated_at": "2026-05-04T10:02:00",
    }
    assert repository.calls == [
        ("get_active_map_profile",),
        (
            "upsert_waypoint",
            "map_0504",
            "corridor_02",
            None,
            "복도2",
            "CORRIDOR",
            0.42,
            -0.52,
            0.0,
            "map",
            "main_corridor",
            True,
        ),
    ]


def test_fms_upsert_waypoint_reports_stale_conflict():
    repository = FakeFmsConfigRepository()
    repository.upsert_result = {
        "status": "STALE",
        "waypoint": repository.waypoints[0],
    }

    response = _service(repository).upsert_waypoint(
        waypoint_id="corridor_01",
        expected_updated_at="2026-05-04T09:59:00",
        display_name="복도1",
        waypoint_type="CORRIDOR",
        pose_x=0.12,
        pose_y=-0.34,
        pose_yaw=1.57,
        frame_id="map",
        snap_group="main_corridor",
        is_enabled=True,
    )

    assert response["result_code"] == "CONFLICT"
    assert response["reason_code"] == "WAYPOINT_STALE"
    assert response["waypoint"]["waypoint_id"] == "corridor_01"


def test_fms_upsert_waypoint_rejects_frame_mismatch():
    repository = FakeFmsConfigRepository()

    response = _service(repository).upsert_waypoint(
        waypoint_id="corridor_01",
        display_name="복도1",
        waypoint_type="CORRIDOR",
        pose_x=0.12,
        pose_y=-0.34,
        pose_yaw=1.57,
        frame_id="odom",
        snap_group=None,
        is_enabled=True,
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "FRAME_ID_MISMATCH"
    assert repository.calls == [("get_active_map_profile",)]


def test_fms_upsert_edge_creates_or_updates_active_map_edge():
    repository = FakeFmsConfigRepository()

    response = _service(repository).upsert_edge(
        edge_id="edge_corridor_01_02",
        expected_updated_at=None,
        from_waypoint_id="corridor_01",
        to_waypoint_id="corridor_02",
        is_bidirectional=True,
        traversal_cost="1.5",
        priority="10",
        is_enabled=True,
    )

    assert response["result_code"] == "OK"
    assert response["reason_code"] is None
    assert response["edge"] == {
        "edge_id": "edge_corridor_01_02",
        "map_id": "map_0504",
        "from_waypoint_id": "corridor_01",
        "to_waypoint_id": "corridor_02",
        "is_bidirectional": True,
        "traversal_cost": 1.5,
        "priority": 10,
        "is_enabled": True,
        "created_at": "2026-05-04T10:03:00",
        "updated_at": "2026-05-04T10:05:00",
    }
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_waypoints", "map_0504", True),
        (
            "upsert_edge",
            "map_0504",
            "edge_corridor_01_02",
            None,
            "corridor_01",
            "corridor_02",
            True,
            1.5,
            10,
            True,
        ),
    ]


def test_fms_upsert_edge_reports_stale_conflict():
    repository = FakeFmsConfigRepository()
    repository.edge_upsert_result = {
        "status": "STALE",
        "edge": repository.edges[0],
    }

    response = _service(repository).upsert_edge(
        edge_id="edge_corridor_01_02",
        expected_updated_at="2026-05-04T09:59:00",
        from_waypoint_id="corridor_01",
        to_waypoint_id="corridor_02",
        is_bidirectional=True,
        traversal_cost=1.5,
        priority=10,
        is_enabled=True,
    )

    assert response["result_code"] == "CONFLICT"
    assert response["reason_code"] == "EDGE_STALE"
    assert response["edge"]["edge_id"] == "edge_corridor_01_02"


def test_fms_upsert_edge_rejects_missing_endpoint_waypoint():
    repository = FakeFmsConfigRepository()

    response = _service(repository).upsert_edge(
        edge_id="edge_corridor_01_missing",
        from_waypoint_id="corridor_01",
        to_waypoint_id="missing_waypoint",
        is_bidirectional=True,
        traversal_cost=None,
        priority=None,
        is_enabled=True,
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "EDGE_WAYPOINT_NOT_FOUND"
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_waypoints", "map_0504", True),
    ]


def test_fms_upsert_edge_async_uses_async_repository_method():
    repository = FakeFmsConfigRepository()

    async def scenario():
        return await _service(repository).async_upsert_edge(
            edge_id="edge_corridor_01_02",
            from_waypoint_id="corridor_01",
            to_waypoint_id="corridor_02",
            is_bidirectional=True,
            traversal_cost=None,
            priority=None,
            is_enabled=True,
        )

    response = asyncio.run(scenario())

    assert response["result_code"] == "OK"
    assert repository.calls == [
        ("async_get_active_map_profile",),
        ("async_get_waypoints", "map_0504", True),
        ("async_upsert_edge", "map_0504", "edge_corridor_01_02", None),
    ]


def test_fms_upsert_waypoint_async_uses_async_repository_method():
    repository = FakeFmsConfigRepository()

    async def scenario():
        return await _service(repository).async_upsert_waypoint(
            waypoint_id="corridor_03",
            display_name="복도3",
            waypoint_type="CORRIDOR",
            pose_x=0.8,
            pose_y=-0.5,
            pose_yaw=0.0,
            frame_id="map",
            snap_group=None,
            is_enabled=True,
        )

    response = asyncio.run(scenario())

    assert response["result_code"] == "OK"
    assert repository.calls == [
        ("async_get_active_map_profile",),
        ("async_upsert_waypoint", "map_0504", "corridor_03", None),
    ]
