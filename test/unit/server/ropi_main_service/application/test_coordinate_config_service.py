import base64
import hashlib
import asyncio
import json
from datetime import datetime, timezone

from server.ropi_main_service.application.coordinate_config import (
    CoordinateConfigService,
)


class FakeCoordinateConfigRepository:
    def __init__(self):
        self.calls = []
        self.boundary_json = {
            "type": "POLYGON",
            "header": {"frame_id": "map"},
            "vertices": [
                {"x": 1.2, "y": -0.4},
                {"x": 2.2, "y": -0.4},
                {"x": 2.2, "y": 0.5},
                {"x": 1.2, "y": 0.5},
            ],
        }
        self.map_profile = {
            "map_id": "map_test11_0423",
            "map_name": "map_test11_0423",
            "map_revision": "1",
            "git_ref": "demo",
            "yaml_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.yaml",
            "pgm_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.pgm",
            "frame_id": "",
            "is_active": 1,
        }
        self.map_profiles_by_id = {
            "map_test11_0423": self.map_profile,
        }
        self.operation_zones = [
            {
                "zone_id": "room_301",
                "map_id": "map_test11_0423",
                "zone_name": "301호",
                "zone_type": "ROOM",
                "revision": "2",
                "boundary_json": json.dumps(self.boundary_json),
                "is_enabled": 1,
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 1, 0),
            }
        ]
        self.goal_poses = [
            {
                "goal_pose_id": "delivery_room_301",
                "map_id": "map_test11_0423",
                "zone_id": "room_301",
                "zone_name": "301호",
                "purpose": "DESTINATION",
                "pose_x": "1.6946",
                "pose_y": "0.0043",
                "pose_yaw": "0",
                "frame_id": "",
                "is_enabled": 1,
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 1, 0),
            }
        ]
        self.patrol_areas = [
            {
                "patrol_area_id": "patrol_ward_night_01",
                "map_id": "map_test11_0423",
                "patrol_area_name": "야간 병동 순찰",
                "revision": "7",
                "path_json": json.dumps(
                    {
                        "header": {"frame_id": "map"},
                        "poses": [
                            {"x": 0.1666, "y": -0.4497, "yaw": 1.5708},
                            {"x": 1.6946, "y": 0.0043, "yaw": 0.0},
                        ],
                    }
                ),
                "waypoint_count": None,
                "path_frame_id": None,
                "is_enabled": 1,
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 1, 0),
            }
        ]
        self.existing_zone = None
        self.create_result = None
        self.update_result = None
        self.boundary_update_result = None
        self.goal_pose_update_result = None
        self.goal_pose_create_result = None
        self.patrol_area_update_result = None
        self.existing_goal_pose = None
        self.existing_patrol_area = None

    def get_active_map_profile(self):
        self.calls.append(("get_active_map_profile",))
        return self.map_profile

    async def async_get_active_map_profile(self):
        self.calls.append(("async_get_active_map_profile",))
        return self.map_profile

    def get_map_profile(self, *, map_id):
        self.calls.append(("get_map_profile", map_id))
        return self.map_profiles_by_id.get(map_id)

    async def async_get_map_profile(self, *, map_id):
        self.calls.append(("async_get_map_profile", map_id))
        return self.map_profiles_by_id.get(map_id)

    def list_map_profiles(self):
        self.calls.append(("list_map_profiles",))
        return list(self.map_profiles_by_id.values())

    async def async_list_map_profiles(self):
        self.calls.append(("async_list_map_profiles",))
        return list(self.map_profiles_by_id.values())

    def get_operation_zones(self, *, map_id, include_disabled=True):
        self.calls.append(("get_operation_zones", map_id, include_disabled))
        return self.operation_zones

    async def async_get_operation_zones(self, *, map_id, include_disabled=True):
        self.calls.append(("async_get_operation_zones", map_id, include_disabled))
        return self.operation_zones

    def get_goal_poses(self, *, map_id, include_disabled=True):
        self.calls.append(("get_goal_poses", map_id, include_disabled))
        return self.goal_poses

    async def async_get_goal_poses(self, *, map_id, include_disabled=True):
        self.calls.append(("async_get_goal_poses", map_id, include_disabled))
        return self.goal_poses

    def get_goal_pose(self, *, goal_pose_id):
        self.calls.append(("get_goal_pose", goal_pose_id))
        return self.existing_goal_pose

    async def async_get_goal_pose(self, *, goal_pose_id):
        self.calls.append(("async_get_goal_pose", goal_pose_id))
        return self.existing_goal_pose

    def get_patrol_areas(self, *, map_id, include_disabled=True):
        self.calls.append(("get_patrol_areas", map_id, include_disabled))
        return self.patrol_areas

    async def async_get_patrol_areas(self, *, map_id, include_disabled=True):
        self.calls.append(("async_get_patrol_areas", map_id, include_disabled))
        return self.patrol_areas

    def get_patrol_area(self, *, patrol_area_id):
        self.calls.append(("get_patrol_area", patrol_area_id))
        return self.existing_patrol_area

    async def async_get_patrol_area(self, *, patrol_area_id):
        self.calls.append(("async_get_patrol_area", patrol_area_id))
        return self.existing_patrol_area

    def get_operation_zone(self, *, map_id, zone_id):
        self.calls.append(("get_operation_zone", map_id, zone_id))
        return self.existing_zone

    async def async_get_operation_zone(self, *, map_id, zone_id):
        self.calls.append(("async_get_operation_zone", map_id, zone_id))
        return self.existing_zone

    def create_operation_zone(
        self,
        *,
        map_id,
        zone_id,
        zone_name,
        zone_type,
        is_enabled=True,
    ):
        self.calls.append(
            (
                "create_operation_zone",
                map_id,
                zone_id,
                zone_name,
                zone_type,
                is_enabled,
            )
        )
        return self.create_result or {
            "zone_id": zone_id,
            "map_id": map_id,
            "zone_name": zone_name,
            "zone_type": zone_type,
            "revision": 1,
            "boundary_json": None,
            "is_enabled": is_enabled,
            "created_at": datetime(2026, 5, 2, 12, 2, 0),
            "updated_at": datetime(2026, 5, 2, 12, 2, 0),
        }

    async def async_create_operation_zone(self, **kwargs):
        self.calls.append(
            (
                "async_create_operation_zone",
                kwargs["map_id"],
                kwargs["zone_id"],
                kwargs["zone_name"],
                kwargs["zone_type"],
                kwargs["is_enabled"],
            )
        )
        return self.create_result or {
            "zone_id": kwargs["zone_id"],
            "map_id": kwargs["map_id"],
            "zone_name": kwargs["zone_name"],
            "zone_type": kwargs["zone_type"],
            "revision": 1,
            "boundary_json": None,
            "is_enabled": kwargs["is_enabled"],
            "created_at": datetime(2026, 5, 2, 12, 2, 0),
            "updated_at": datetime(2026, 5, 2, 12, 2, 0),
        }

    def update_operation_zone(
        self,
        *,
        map_id,
        zone_id,
        expected_revision,
        zone_name,
        zone_type,
        is_enabled,
    ):
        self.calls.append(
            (
                "update_operation_zone",
                map_id,
                zone_id,
                expected_revision,
                zone_name,
                zone_type,
                is_enabled,
            )
        )
        return self.update_result or {
            "status": "UPDATED",
            "operation_zone": {
                "zone_id": zone_id,
                "map_id": map_id,
                "zone_name": zone_name,
                "zone_type": zone_type,
                "revision": expected_revision + 1,
                "boundary_json": None,
                "is_enabled": is_enabled,
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 3, 0),
            },
        }

    async def async_update_operation_zone(self, **kwargs):
        self.calls.append(
            (
                "async_update_operation_zone",
                kwargs["map_id"],
                kwargs["zone_id"],
                kwargs["expected_revision"],
                kwargs["zone_name"],
                kwargs["zone_type"],
                kwargs["is_enabled"],
            )
        )
        return self.update_result or {
            "status": "UPDATED",
            "operation_zone": {
                "zone_id": kwargs["zone_id"],
                "map_id": kwargs["map_id"],
                "zone_name": kwargs["zone_name"],
                "zone_type": kwargs["zone_type"],
                "revision": kwargs["expected_revision"] + 1,
                "boundary_json": None,
                "is_enabled": kwargs["is_enabled"],
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 3, 0),
            },
        }

    def update_operation_zone_boundary(
        self,
        *,
        map_id,
        zone_id,
        expected_revision,
        boundary_json,
    ):
        self.calls.append(
            (
                "update_operation_zone_boundary",
                map_id,
                zone_id,
                expected_revision,
                boundary_json,
            )
        )
        stored_boundary = (
            json.dumps(boundary_json) if boundary_json is not None else None
        )
        return self.boundary_update_result or {
            "status": "UPDATED",
            "operation_zone": {
                "zone_id": zone_id,
                "map_id": map_id,
                "zone_name": "301호",
                "zone_type": "ROOM",
                "revision": expected_revision + 1,
                "boundary_json": stored_boundary,
                "is_enabled": True,
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 6, 0),
            },
        }

    async def async_update_operation_zone_boundary(self, **kwargs):
        self.calls.append(
            (
                "async_update_operation_zone_boundary",
                kwargs["map_id"],
                kwargs["zone_id"],
                kwargs["expected_revision"],
                kwargs["boundary_json"],
            )
        )
        stored_boundary = (
            json.dumps(kwargs["boundary_json"])
            if kwargs["boundary_json"] is not None
            else None
        )
        return self.boundary_update_result or {
            "status": "UPDATED",
            "operation_zone": {
                "zone_id": kwargs["zone_id"],
                "map_id": kwargs["map_id"],
                "zone_name": "301호",
                "zone_type": "ROOM",
                "revision": kwargs["expected_revision"] + 1,
                "boundary_json": stored_boundary,
                "is_enabled": True,
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 6, 0),
            },
        }

    def create_patrol_area(
        self,
        *,
        map_id,
        patrol_area_id,
        patrol_area_name,
        path_json,
        is_enabled=True,
    ):
        self.calls.append(
            (
                "create_patrol_area",
                map_id,
                patrol_area_id,
                patrol_area_name,
                path_json,
                is_enabled,
            )
        )
        return {
            "patrol_area_id": patrol_area_id,
            "map_id": map_id,
            "patrol_area_name": patrol_area_name,
            "revision": 1,
            "path_json": path_json,
            "waypoint_count": len(path_json["poses"]),
            "path_frame_id": path_json["header"]["frame_id"],
            "is_enabled": is_enabled,
            "created_at": datetime(2026, 5, 2, 12, 2, 0),
            "updated_at": datetime(2026, 5, 2, 12, 2, 0),
        }

    async def async_create_patrol_area(self, **kwargs):
        self.calls.append(
            (
                "async_create_patrol_area",
                kwargs["map_id"],
                kwargs["patrol_area_id"],
                kwargs["patrol_area_name"],
                kwargs["path_json"],
                kwargs["is_enabled"],
            )
        )
        return {
            "patrol_area_id": kwargs["patrol_area_id"],
            "map_id": kwargs["map_id"],
            "patrol_area_name": kwargs["patrol_area_name"],
            "revision": 1,
            "path_json": kwargs["path_json"],
            "waypoint_count": len(kwargs["path_json"]["poses"]),
            "path_frame_id": kwargs["path_json"]["header"]["frame_id"],
            "is_enabled": kwargs["is_enabled"],
            "created_at": datetime(2026, 5, 2, 12, 2, 0),
            "updated_at": datetime(2026, 5, 2, 12, 2, 0),
        }

    def update_patrol_area(
        self,
        *,
        map_id,
        patrol_area_id,
        expected_revision,
        patrol_area_name,
        path_json,
        is_enabled,
    ):
        self.calls.append(
            (
                "update_patrol_area",
                map_id,
                patrol_area_id,
                expected_revision,
                patrol_area_name,
                path_json,
                is_enabled,
            )
        )
        return self.patrol_area_update_result or {
            "status": "UPDATED",
            "patrol_area": {
                "patrol_area_id": patrol_area_id,
                "map_id": map_id,
                "patrol_area_name": patrol_area_name,
                "revision": expected_revision + 1,
                "path_json": path_json,
                "waypoint_count": len(path_json["poses"]),
                "path_frame_id": path_json["header"]["frame_id"],
                "is_enabled": is_enabled,
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 5, 0),
            },
        }

    async def async_update_patrol_area(self, **kwargs):
        self.calls.append(
            (
                "async_update_patrol_area",
                kwargs["map_id"],
                kwargs["patrol_area_id"],
                kwargs["expected_revision"],
                kwargs["patrol_area_name"],
                kwargs["path_json"],
                kwargs["is_enabled"],
            )
        )
        return self.patrol_area_update_result or {
            "status": "UPDATED",
            "patrol_area": {
                "patrol_area_id": kwargs["patrol_area_id"],
                "map_id": kwargs["map_id"],
                "patrol_area_name": kwargs["patrol_area_name"],
                "revision": kwargs["expected_revision"] + 1,
                "path_json": kwargs["path_json"],
                "waypoint_count": len(kwargs["path_json"]["poses"]),
                "path_frame_id": kwargs["path_json"]["header"]["frame_id"],
                "is_enabled": kwargs["is_enabled"],
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 5, 0),
            },
        }

    def update_goal_pose(
        self,
        *,
        map_id,
        goal_pose_id,
        expected_updated_at,
        zone_id,
        purpose,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        is_enabled,
    ):
        self.calls.append(
            (
                "update_goal_pose",
                map_id,
                goal_pose_id,
                expected_updated_at,
                zone_id,
                purpose,
                pose_x,
                pose_y,
                pose_yaw,
                frame_id,
                is_enabled,
            )
        )
        return self.goal_pose_update_result or {
            "status": "UPDATED",
            "goal_pose": {
                "goal_pose_id": goal_pose_id,
                "map_id": map_id,
                "zone_id": zone_id,
                "zone_name": "301호" if zone_id == "room_301" else None,
                "purpose": purpose,
                "pose_x": pose_x,
                "pose_y": pose_y,
                "pose_yaw": pose_yaw,
                "frame_id": frame_id,
                "is_enabled": is_enabled,
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 4, 0),
            },
        }

    async def async_update_goal_pose(self, **kwargs):
        self.calls.append(
            (
                "async_update_goal_pose",
                kwargs["map_id"],
                kwargs["goal_pose_id"],
                kwargs["expected_updated_at"],
                kwargs["zone_id"],
                kwargs["purpose"],
                kwargs["pose_x"],
                kwargs["pose_y"],
                kwargs["pose_yaw"],
                kwargs["frame_id"],
                kwargs["is_enabled"],
            )
        )
        return self.goal_pose_update_result or {
            "status": "UPDATED",
            "goal_pose": {
                "goal_pose_id": kwargs["goal_pose_id"],
                "map_id": kwargs["map_id"],
                "zone_id": kwargs["zone_id"],
                "zone_name": "301호" if kwargs["zone_id"] == "room_301" else None,
                "purpose": kwargs["purpose"],
                "pose_x": kwargs["pose_x"],
                "pose_y": kwargs["pose_y"],
                "pose_yaw": kwargs["pose_yaw"],
                "frame_id": kwargs["frame_id"],
                "is_enabled": kwargs["is_enabled"],
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 4, 0),
            },
        }

    def create_goal_pose(
        self,
        *,
        map_id,
        goal_pose_id,
        zone_id,
        purpose,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        is_enabled=True,
    ):
        self.calls.append(
            (
                "create_goal_pose",
                map_id,
                goal_pose_id,
                zone_id,
                purpose,
                pose_x,
                pose_y,
                pose_yaw,
                frame_id,
                is_enabled,
            )
        )
        return self.goal_pose_create_result or {
            "goal_pose_id": goal_pose_id,
            "map_id": map_id,
            "zone_id": zone_id,
            "zone_name": "301호" if zone_id == "room_301" else None,
            "purpose": purpose,
            "pose_x": pose_x,
            "pose_y": pose_y,
            "pose_yaw": pose_yaw,
            "frame_id": frame_id,
            "is_enabled": is_enabled,
            "created_at": datetime(2026, 5, 2, 12, 2, 0),
            "updated_at": datetime(2026, 5, 2, 12, 2, 0),
        }

    async def async_create_goal_pose(self, **kwargs):
        self.calls.append(
            (
                "async_create_goal_pose",
                kwargs["map_id"],
                kwargs["goal_pose_id"],
                kwargs["zone_id"],
                kwargs["purpose"],
                kwargs["pose_x"],
                kwargs["pose_y"],
                kwargs["pose_yaw"],
                kwargs["frame_id"],
                kwargs["is_enabled"],
            )
        )
        return self.goal_pose_create_result or {
            "goal_pose_id": kwargs["goal_pose_id"],
            "map_id": kwargs["map_id"],
            "zone_id": kwargs["zone_id"],
            "zone_name": "301호" if kwargs["zone_id"] == "room_301" else None,
            "purpose": kwargs["purpose"],
            "pose_x": kwargs["pose_x"],
            "pose_y": kwargs["pose_y"],
            "pose_yaw": kwargs["pose_yaw"],
            "frame_id": kwargs["frame_id"],
            "is_enabled": kwargs["is_enabled"],
            "created_at": datetime(2026, 5, 2, 12, 2, 0),
            "updated_at": datetime(2026, 5, 2, 12, 2, 0),
        }

    def update_patrol_area_path(
        self,
        *,
        map_id,
        patrol_area_id,
        expected_revision,
        path_json,
    ):
        self.calls.append(
            (
                "update_patrol_area_path",
                map_id,
                patrol_area_id,
                expected_revision,
                path_json,
            )
        )
        return self.patrol_area_update_result or {
            "status": "UPDATED",
            "patrol_area": {
                "patrol_area_id": patrol_area_id,
                "map_id": map_id,
                "patrol_area_name": "야간 병동 순찰",
                "revision": expected_revision + 1,
                "path_json": path_json,
                "waypoint_count": len(path_json["poses"]),
                "path_frame_id": path_json["header"]["frame_id"],
                "is_enabled": True,
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 5, 0),
            },
        }

    async def async_update_patrol_area_path(self, **kwargs):
        self.calls.append(
            (
                "async_update_patrol_area_path",
                kwargs["map_id"],
                kwargs["patrol_area_id"],
                kwargs["expected_revision"],
                kwargs["path_json"],
            )
        )
        path_json = kwargs["path_json"]
        return self.patrol_area_update_result or {
            "status": "UPDATED",
            "patrol_area": {
                "patrol_area_id": kwargs["patrol_area_id"],
                "map_id": kwargs["map_id"],
                "patrol_area_name": "야간 병동 순찰",
                "revision": kwargs["expected_revision"] + 1,
                "path_json": path_json,
                "waypoint_count": len(path_json["poses"]),
                "path_frame_id": path_json["header"]["frame_id"],
                "is_enabled": True,
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 5, 0),
            },
        }


def _service(repository):
    return CoordinateConfigService(
        repository=repository,
        clock=lambda: datetime(2026, 5, 2, 3, 10, 0, tzinfo=timezone.utc),
    )


def test_active_map_bundle_formats_active_map_coordinate_data():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).get_active_map_bundle()

    assert response["result_code"] == "OK"
    assert response["result_message"] is None
    assert response["reason_code"] is None
    assert response["generated_at"] == "2026-05-02T03:10:00+00:00"
    assert response["map_profile"] == {
        "map_id": "map_test11_0423",
        "map_name": "map_test11_0423",
        "map_revision": 1,
        "frame_id": "map",
        "yaml_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.yaml",
        "pgm_path": "device/ropi_mobile/src/ropi_nav_config/maps/map_test11_0423.pgm",
        "is_active": True,
    }
    assert response["operation_zones"] == [
        {
            "zone_id": "room_301",
            "map_id": "map_test11_0423",
            "zone_name": "301호",
            "zone_type": "ROOM",
            "revision": 2,
            "boundary_json": repository.boundary_json,
            "boundary_vertex_count": 4,
            "boundary_frame_id": "map",
            "is_enabled": True,
            "created_at": "2026-05-02T12:00:00",
            "updated_at": "2026-05-02T12:01:00",
        }
    ]
    assert response["goal_poses"] == [
        {
            "goal_pose_id": "delivery_room_301",
            "map_id": "map_test11_0423",
            "zone_id": "room_301",
            "zone_name": "301호",
            "purpose": "DESTINATION",
            "pose_x": 1.6946,
            "pose_y": 0.0043,
            "pose_yaw": 0.0,
            "frame_id": "map",
            "is_enabled": True,
            "created_at": "2026-05-02T12:00:00",
            "updated_at": "2026-05-02T12:01:00",
        }
    ]
    assert response["patrol_areas"] == [
        {
            "patrol_area_id": "patrol_ward_night_01",
            "map_id": "map_test11_0423",
            "patrol_area_name": "야간 병동 순찰",
            "revision": 7,
            "path_json": {
                "header": {"frame_id": "map"},
                "poses": [
                    {"x": 0.1666, "y": -0.4497, "yaw": 1.5708},
                    {"x": 1.6946, "y": 0.0043, "yaw": 0.0},
                ],
            },
            "waypoint_count": 2,
            "path_frame_id": "map",
            "is_enabled": True,
            "created_at": "2026-05-02T12:00:00",
            "updated_at": "2026-05-02T12:01:00",
        }
    ]
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_operation_zones", "map_test11_0423", True),
        ("get_goal_poses", "map_test11_0423", True),
        ("get_patrol_areas", "map_test11_0423", True),
        ("list_map_profiles",),
    ]


def test_active_map_bundle_returns_not_found_without_active_map():
    repository = FakeCoordinateConfigRepository()
    repository.map_profile = None

    response = _service(repository).get_active_map_bundle()

    assert response["result_code"] == "NOT_FOUND"
    assert response["reason_code"] == "ACTIVE_MAP_NOT_FOUND"
    assert response["map_profile"] is None
    assert response["operation_zones"] == []
    assert response["goal_poses"] == []
    assert response["patrol_areas"] == []
    assert repository.calls == [("get_active_map_profile",), ("list_map_profiles",)]


def test_selected_map_bundle_reports_missing_requested_map():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).get_map_bundle(map_id="missing_map")

    assert response["result_code"] == "NOT_FOUND"
    assert response["reason_code"] == "MAP_NOT_FOUND"
    assert response["result_message"] == "요청한 map_id를 찾을 수 없습니다."
    assert response["map_profile"] is None
    assert response["map_profiles"][0]["map_id"] == "map_test11_0423"
    assert response["operation_zones"] == []
    assert response["goal_poses"] == []
    assert response["patrol_areas"] == []
    assert repository.calls == [
        ("get_map_profile", "missing_map"),
        ("list_map_profiles",),
    ]


def test_active_map_bundle_async_uses_async_repository_methods():
    repository = FakeCoordinateConfigRepository()

    response = asyncio.run(
        _service(repository).async_get_active_map_bundle(
            include_disabled=False,
            include_patrol_paths=False,
        )
    )

    assert response["result_code"] == "OK"
    assert response["patrol_areas"][0]["path_json"] is None
    assert repository.calls == [
        ("async_get_active_map_profile",),
        ("async_get_operation_zones", "map_test11_0423", False),
        ("async_get_goal_poses", "map_test11_0423", False),
        ("async_get_patrol_areas", "map_test11_0423", False),
        ("list_map_profiles",),
    ]


def test_active_map_bundle_can_omit_boundary_payloads():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).get_active_map_bundle(
        include_zone_boundaries=False,
    )

    assert response["result_code"] == "OK"
    assert response["operation_zones"][0]["boundary_json"] is None
    assert response["operation_zones"][0]["boundary_vertex_count"] == 4
    assert response["operation_zones"][0]["boundary_frame_id"] == "map"


def test_create_operation_zone_creates_zone_on_active_map():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).create_operation_zone(
        zone_id="caregiver_room",
        zone_name="보호사실",
        zone_type="staff_station",
        is_enabled=True,
    )

    assert response["result_code"] == "CREATED"
    assert response["reason_code"] is None
    assert response["operation_zone"] == {
        "zone_id": "caregiver_room",
        "map_id": "map_test11_0423",
        "zone_name": "보호사실",
        "zone_type": "STAFF_STATION",
        "revision": 1,
        "boundary_json": None,
        "boundary_vertex_count": 0,
        "boundary_frame_id": None,
        "is_enabled": True,
        "created_at": "2026-05-02T12:02:00",
        "updated_at": "2026-05-02T12:02:00",
    }
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_operation_zone", "map_test11_0423", "caregiver_room"),
        (
            "create_operation_zone",
            "map_test11_0423",
            "caregiver_room",
            "보호사실",
            "STAFF_STATION",
            True,
        ),
    ]


def test_create_operation_zone_rejects_duplicate_zone_id():
    repository = FakeCoordinateConfigRepository()
    repository.existing_zone = repository.operation_zones[0]

    response = _service(repository).create_operation_zone(
        zone_id="room_301",
        zone_name="301호",
        zone_type="ROOM",
    )

    assert response["result_code"] == "CONFLICT"
    assert response["reason_code"] == "ZONE_ID_DUPLICATED"
    assert response["operation_zone"] is None
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_operation_zone", "map_test11_0423", "room_301"),
    ]


def test_create_operation_zone_rejects_missing_map_id():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).create_operation_zone(
        zone_id="caregiver_room",
        zone_name="보호사실",
        zone_type="STAFF_STATION",
        map_id="other_map",
    )

    assert response["result_code"] == "NOT_FOUND"
    assert response["reason_code"] == "MAP_NOT_FOUND"
    assert response["operation_zone"] is None
    assert repository.calls == [("get_map_profile", "other_map")]


def test_create_operation_zone_rejects_invalid_zone_type():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).create_operation_zone(
        zone_id="caregiver_room",
        zone_name="보호사실",
        zone_type="unknown",
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "ZONE_TYPE_INVALID"
    assert response["operation_zone"] is None
    assert repository.calls == [("get_active_map_profile",)]


def test_update_operation_zone_updates_zone_with_revision_check():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).update_operation_zone(
        zone_id="room_301",
        expected_revision=1,
        zone_name="301호",
        zone_type="ROOM",
        is_enabled=False,
    )

    assert response["result_code"] == "UPDATED"
    assert response["reason_code"] is None
    assert response["operation_zone"] == {
        "zone_id": "room_301",
        "map_id": "map_test11_0423",
        "zone_name": "301호",
        "zone_type": "ROOM",
        "revision": 2,
        "boundary_json": None,
        "boundary_vertex_count": 0,
        "boundary_frame_id": None,
        "is_enabled": False,
        "created_at": "2026-05-02T12:00:00",
        "updated_at": "2026-05-02T12:03:00",
    }
    assert repository.calls == [
        ("get_active_map_profile",),
        (
            "update_operation_zone",
            "map_test11_0423",
            "room_301",
            1,
            "301호",
            "ROOM",
            False,
        ),
    ]


def test_update_operation_zone_reports_revision_conflict():
    repository = FakeCoordinateConfigRepository()
    repository.update_result = {
        "status": "REVISION_CONFLICT",
        "operation_zone": repository.operation_zones[0],
    }

    response = _service(repository).update_operation_zone(
        zone_id="room_301",
        expected_revision=1,
        zone_name="301호",
        zone_type="ROOM",
        is_enabled=True,
    )

    assert response["result_code"] == "CONFLICT"
    assert response["reason_code"] == "ZONE_REVISION_CONFLICT"
    assert response["operation_zone"] is None


def test_update_operation_zone_async_uses_async_repository_method():
    repository = FakeCoordinateConfigRepository()

    response = asyncio.run(
        _service(repository).async_update_operation_zone(
            zone_id="room_301",
            expected_revision="1",
            zone_name="301호",
            zone_type="room",
            is_enabled="false",
        )
    )

    assert response["result_code"] == "UPDATED"
    assert response["operation_zone"]["revision"] == 2
    assert response["operation_zone"]["is_enabled"] is False
    assert repository.calls == [
        ("async_get_active_map_profile",),
        (
            "async_update_operation_zone",
            "map_test11_0423",
            "room_301",
            1,
            "301호",
            "ROOM",
            False,
        ),
    ]


def test_update_operation_zone_boundary_replaces_polygon_with_revision_check():
    repository = FakeCoordinateConfigRepository()
    boundary_json = {
        "type": "polygon",
        "header": {"frame_id": "map"},
        "vertices": [
            {"x": "1.0", "y": "0.0"},
            {"x": "2.0", "y": "0.0"},
            {"x": "2.0", "y": "1.0"},
        ],
    }

    response = _service(repository).update_operation_zone_boundary(
        zone_id="room_301",
        expected_revision="2",
        boundary_json=boundary_json,
    )

    normalized_boundary = {
        "type": "POLYGON",
        "header": {"frame_id": "map"},
        "vertices": [
            {"x": 1.0, "y": 0.0},
            {"x": 2.0, "y": 0.0},
            {"x": 2.0, "y": 1.0},
        ],
    }
    assert response["result_code"] == "UPDATED"
    assert response["reason_code"] is None
    assert response["operation_zone"] == {
        "zone_id": "room_301",
        "map_id": "map_test11_0423",
        "zone_name": "301호",
        "zone_type": "ROOM",
        "revision": 3,
        "boundary_json": normalized_boundary,
        "boundary_vertex_count": 3,
        "boundary_frame_id": "map",
        "is_enabled": True,
        "created_at": "2026-05-02T12:00:00",
        "updated_at": "2026-05-02T12:06:00",
    }
    assert repository.calls == [
        ("get_active_map_profile",),
        (
            "update_operation_zone_boundary",
            "map_test11_0423",
            "room_301",
            2,
            normalized_boundary,
        ),
    ]


def test_update_operation_zone_boundary_clears_boundary():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).update_operation_zone_boundary(
        zone_id="room_301",
        expected_revision=2,
        boundary_json=None,
    )

    assert response["result_code"] == "UPDATED"
    assert response["operation_zone"]["boundary_json"] is None
    assert response["operation_zone"]["boundary_vertex_count"] == 0
    assert repository.calls[-1] == (
        "update_operation_zone_boundary",
        "map_test11_0423",
        "room_301",
        2,
        None,
    )


def test_update_operation_zone_boundary_rejects_too_few_vertices():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).update_operation_zone_boundary(
        zone_id="room_301",
        expected_revision=2,
        boundary_json={
            "type": "POLYGON",
            "header": {"frame_id": "map"},
            "vertices": [
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
            ],
        },
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "ZONE_BOUNDARY_TOO_SHORT"
    assert response["operation_zone"] is None
    assert repository.calls == [("get_active_map_profile",)]


def test_update_operation_zone_boundary_rejects_frame_mismatch():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).update_operation_zone_boundary(
        zone_id="room_301",
        expected_revision=2,
        boundary_json={
            "type": "POLYGON",
            "header": {"frame_id": "odom"},
            "vertices": [
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 1.0},
            ],
        },
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "FRAME_ID_MISMATCH"
    assert response["operation_zone"] is None
    assert repository.calls == [("get_active_map_profile",)]


def test_update_operation_zone_boundary_reports_revision_conflict():
    repository = FakeCoordinateConfigRepository()
    repository.boundary_update_result = {
        "status": "REVISION_CONFLICT",
        "operation_zone": repository.operation_zones[0],
    }

    response = _service(repository).update_operation_zone_boundary(
        zone_id="room_301",
        expected_revision=1,
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

    assert response["result_code"] == "CONFLICT"
    assert response["reason_code"] == "ZONE_REVISION_CONFLICT"
    assert response["operation_zone"] is None


def test_update_operation_zone_boundary_async_uses_async_repository_method():
    repository = FakeCoordinateConfigRepository()

    response = asyncio.run(
        _service(repository).async_update_operation_zone_boundary(
            zone_id="room_301",
            expected_revision="2",
            boundary_json={
                "type": "POLYGON",
                "header": {"frame_id": "map"},
                "vertices": [
                    {"x": "0.0", "y": "0.0"},
                    {"x": "1.0", "y": "0.0"},
                    {"x": "1.0", "y": "1.0"},
                ],
            },
        )
    )

    assert response["result_code"] == "UPDATED"
    assert response["operation_zone"]["revision"] == 3
    assert repository.calls == [
        ("async_get_active_map_profile",),
        (
            "async_update_operation_zone_boundary",
            "map_test11_0423",
            "room_301",
            2,
            {
                "type": "POLYGON",
                "header": {"frame_id": "map"},
                "vertices": [
                    {"x": 0.0, "y": 0.0},
                    {"x": 1.0, "y": 0.0},
                    {"x": 1.0, "y": 1.0},
                ],
            },
        ),
    ]


def test_update_goal_pose_updates_existing_pose_on_active_map():
    repository = FakeCoordinateConfigRepository()
    repository.existing_zone = repository.operation_zones[0]

    response = _service(repository).update_goal_pose(
        goal_pose_id="delivery_room_301",
        expected_updated_at="2026-05-02T12:01:00",
        zone_id="room_301",
        purpose="destination",
        pose_x="1.7",
        pose_y="0.02",
        pose_yaw="0",
        frame_id="map",
        is_enabled=True,
    )

    assert response["result_code"] == "UPDATED"
    assert response["reason_code"] is None
    assert response["goal_pose"] == {
        "goal_pose_id": "delivery_room_301",
        "map_id": "map_test11_0423",
        "zone_id": "room_301",
        "zone_name": "301호",
        "purpose": "DESTINATION",
        "pose_x": 1.7,
        "pose_y": 0.02,
        "pose_yaw": 0.0,
        "frame_id": "map",
        "is_enabled": True,
        "created_at": "2026-05-02T12:00:00",
        "updated_at": "2026-05-02T12:04:00",
    }
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_operation_zone", "map_test11_0423", "room_301"),
        (
            "update_goal_pose",
            "map_test11_0423",
            "delivery_room_301",
            "2026-05-02T12:01:00",
            "room_301",
            "DESTINATION",
            1.7,
            0.02,
            0.0,
            "map",
            True,
        ),
    ]


def test_update_goal_pose_rejects_frame_mismatch():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).update_goal_pose(
        goal_pose_id="delivery_room_301",
        expected_updated_at=None,
        zone_id=None,
        purpose="DESTINATION",
        pose_x=1.7,
        pose_y=0.02,
        pose_yaw=0.0,
        frame_id="odom",
        is_enabled=True,
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "FRAME_ID_MISMATCH"
    assert response["goal_pose"] is None
    assert repository.calls == [("get_active_map_profile",)]


def test_update_goal_pose_rejects_invalid_purpose():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).update_goal_pose(
        goal_pose_id="delivery_room_301",
        expected_updated_at=None,
        zone_id=None,
        purpose="GUIDE",
        pose_x=1.7,
        pose_y=0.02,
        pose_yaw=0.0,
        frame_id="map",
        is_enabled=True,
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "GOAL_POSE_PURPOSE_INVALID"
    assert response["goal_pose"] is None
    assert repository.calls == [("get_active_map_profile",)]


def test_update_goal_pose_rejects_missing_zone():
    repository = FakeCoordinateConfigRepository()
    repository.existing_zone = None

    response = _service(repository).update_goal_pose(
        goal_pose_id="delivery_room_301",
        expected_updated_at=None,
        zone_id="room_999",
        purpose="DESTINATION",
        pose_x=1.7,
        pose_y=0.02,
        pose_yaw=0.0,
        frame_id="map",
        is_enabled=True,
    )

    assert response["result_code"] == "NOT_FOUND"
    assert response["reason_code"] == "ZONE_NOT_FOUND"
    assert response["goal_pose"] is None
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_operation_zone", "map_test11_0423", "room_999"),
    ]


def test_update_goal_pose_reports_stale_write_conflict():
    repository = FakeCoordinateConfigRepository()
    repository.goal_pose_update_result = {
        "status": "STALE",
        "goal_pose": repository.goal_poses[0],
    }

    response = _service(repository).update_goal_pose(
        goal_pose_id="delivery_room_301",
        expected_updated_at="2026-05-02T12:00:00",
        zone_id=None,
        purpose="DESTINATION",
        pose_x=1.7,
        pose_y=0.02,
        pose_yaw=0.0,
        frame_id="map",
        is_enabled=True,
    )

    assert response["result_code"] == "CONFLICT"
    assert response["reason_code"] == "GOAL_POSE_STALE"
    assert response["goal_pose"] is None


def test_update_goal_pose_async_uses_async_repository_method():
    repository = FakeCoordinateConfigRepository()
    repository.existing_zone = repository.operation_zones[0]

    response = asyncio.run(
        _service(repository).async_update_goal_pose(
            goal_pose_id="delivery_room_301",
            expected_updated_at=None,
            zone_id="room_301",
            purpose="destination",
            pose_x="1.7",
            pose_y="0.02",
            pose_yaw="0",
            frame_id="map",
            is_enabled="false",
        )
    )

    assert response["result_code"] == "UPDATED"
    assert response["goal_pose"]["is_enabled"] is False
    assert repository.calls == [
        ("async_get_active_map_profile",),
        ("async_get_operation_zone", "map_test11_0423", "room_301"),
        (
            "async_update_goal_pose",
            "map_test11_0423",
            "delivery_room_301",
            None,
            "room_301",
            "DESTINATION",
            1.7,
            0.02,
            0.0,
            "map",
            False,
        ),
    ]


def test_create_goal_pose_creates_active_map_row():
    repository = FakeCoordinateConfigRepository()
    repository.existing_zone = repository.operation_zones[0]

    response = _service(repository).create_goal_pose(
        goal_pose_id="delivery_room_302",
        zone_id="room_301",
        purpose="destination",
        pose_x="2.1",
        pose_y="0.12",
        pose_yaw="0",
        frame_id="map",
        is_enabled=True,
    )

    assert response["result_code"] == "CREATED"
    assert response["reason_code"] is None
    assert response["goal_pose"] == {
        "goal_pose_id": "delivery_room_302",
        "map_id": "map_test11_0423",
        "zone_id": "room_301",
        "zone_name": "301호",
        "purpose": "DESTINATION",
        "pose_x": 2.1,
        "pose_y": 0.12,
        "pose_yaw": 0.0,
        "frame_id": "map",
        "is_enabled": True,
        "created_at": "2026-05-02T12:02:00",
        "updated_at": "2026-05-02T12:02:00",
    }
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_operation_zone", "map_test11_0423", "room_301"),
        ("get_goal_pose", "delivery_room_302"),
        (
            "create_goal_pose",
            "map_test11_0423",
            "delivery_room_302",
            "room_301",
            "DESTINATION",
            2.1,
            0.12,
            0.0,
            "map",
            True,
        ),
    ]


def test_create_goal_pose_rejects_duplicate_id():
    repository = FakeCoordinateConfigRepository()
    repository.existing_goal_pose = repository.goal_poses[0]

    response = _service(repository).create_goal_pose(
        goal_pose_id="delivery_room_301",
        zone_id=None,
        purpose="DESTINATION",
        pose_x=1.7,
        pose_y=0.02,
        pose_yaw=0.0,
        frame_id="map",
        is_enabled=True,
    )

    assert response["result_code"] == "CONFLICT"
    assert response["reason_code"] == "GOAL_POSE_ID_DUPLICATED"
    assert response["goal_pose"] is None
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_goal_pose", "delivery_room_301"),
    ]


def test_create_goal_pose_async_uses_async_repository_method():
    repository = FakeCoordinateConfigRepository()
    repository.existing_zone = repository.operation_zones[0]

    response = asyncio.run(
        _service(repository).async_create_goal_pose(
            goal_pose_id="delivery_room_302",
            zone_id="room_301",
            purpose="destination",
            pose_x="2.1",
            pose_y="0.12",
            pose_yaw="0",
            frame_id="map",
            is_enabled="false",
        )
    )

    assert response["result_code"] == "CREATED"
    assert response["goal_pose"]["is_enabled"] is False
    assert repository.calls == [
        ("async_get_active_map_profile",),
        ("async_get_operation_zone", "map_test11_0423", "room_301"),
        ("async_get_goal_pose", "delivery_room_302"),
        (
            "async_create_goal_pose",
            "map_test11_0423",
            "delivery_room_302",
            "room_301",
            "DESTINATION",
            2.1,
            0.12,
            0.0,
            "map",
            False,
        ),
    ]


def test_update_patrol_area_path_replaces_path_and_increments_revision():
    repository = FakeCoordinateConfigRepository()
    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": "0.1666", "y": "-0.4497", "yaw": "1.5708"},
            {"x": "1.6946", "y": "0.0043", "yaw": "0"},
        ],
    }

    response = _service(repository).update_patrol_area_path(
        patrol_area_id="patrol_ward_night_01",
        expected_revision="7",
        path_json=path_json,
    )

    normalized_path = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.1666, "y": -0.4497, "yaw": 1.5708},
            {"x": 1.6946, "y": 0.0043, "yaw": 0.0},
        ],
    }
    assert response["result_code"] == "UPDATED"
    assert response["reason_code"] is None
    assert response["patrol_area"] == {
        "patrol_area_id": "patrol_ward_night_01",
        "map_id": "map_test11_0423",
        "patrol_area_name": "야간 병동 순찰",
        "revision": 8,
        "path_json": normalized_path,
        "waypoint_count": 2,
        "path_frame_id": "map",
        "is_enabled": True,
        "created_at": "2026-05-02T12:00:00",
        "updated_at": "2026-05-02T12:05:00",
    }
    assert repository.calls == [
        ("get_active_map_profile",),
        (
            "update_patrol_area_path",
            "map_test11_0423",
            "patrol_ward_night_01",
            7,
            normalized_path,
        ),
    ]


def test_create_patrol_area_creates_active_map_row_with_initial_path():
    repository = FakeCoordinateConfigRepository()
    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 0.0},
        ],
    }

    response = _service(repository).create_patrol_area(
        patrol_area_id="patrol_day_01",
        patrol_area_name="주간 병동 순찰",
        path_json=path_json,
        is_enabled=True,
    )

    assert response["result_code"] == "CREATED"
    assert response["patrol_area"]["patrol_area_id"] == "patrol_day_01"
    assert response["patrol_area"]["revision"] == 1
    assert response["patrol_area"]["waypoint_count"] == 2
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_patrol_area", "patrol_day_01"),
        (
            "create_patrol_area",
            "map_test11_0423",
            "patrol_day_01",
            "주간 병동 순찰",
            path_json,
            True,
        ),
    ]


def test_create_patrol_area_uses_requested_map_id_when_selected_map_is_not_active():
    repository = FakeCoordinateConfigRepository()
    map_profile = dict(repository.map_profile)
    map_profile["map_id"] = "map_test12_0506"
    repository.map_profiles_by_id["map_test12_0506"] = map_profile
    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 0.0},
        ],
    }

    response = _service(repository).create_patrol_area(
        patrol_area_id="transport_patrol_test",
        map_id="map_test12_0506",
        patrol_area_name="운반 맵 점검",
        path_json=path_json,
        is_enabled=True,
    )

    assert response["result_code"] == "CREATED"
    assert response["patrol_area"]["map_id"] == "map_test12_0506"
    assert repository.calls == [
        ("get_map_profile", "map_test12_0506"),
        ("get_patrol_area", "transport_patrol_test"),
        (
            "create_patrol_area",
            "map_test12_0506",
            "transport_patrol_test",
            "운반 맵 점검",
            path_json,
            True,
        ),
    ]


def test_update_patrol_area_updates_name_path_and_enabled_state():
    repository = FakeCoordinateConfigRepository()
    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 0.0},
        ],
    }

    response = _service(repository).update_patrol_area(
        patrol_area_id="patrol_ward_night_01",
        expected_revision="7",
        patrol_area_name="야간 병동 순찰",
        path_json=path_json,
        is_enabled=False,
    )

    assert response["result_code"] == "UPDATED"
    assert response["patrol_area"]["revision"] == 8
    assert response["patrol_area"]["is_enabled"] is False
    assert repository.calls == [
        ("get_active_map_profile",),
        (
            "update_patrol_area",
            "map_test11_0423",
            "patrol_ward_night_01",
            7,
            "야간 병동 순찰",
            path_json,
            False,
        ),
    ]


def test_update_patrol_area_uses_requested_map_id_when_selected_map_is_not_active():
    repository = FakeCoordinateConfigRepository()
    map_profile = dict(repository.map_profile)
    map_profile["map_id"] = "map_test12_0506"
    repository.map_profiles_by_id["map_test12_0506"] = map_profile
    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 0.0},
        ],
    }

    response = _service(repository).update_patrol_area(
        patrol_area_id="transport_patrol_test",
        map_id="map_test12_0506",
        expected_revision="3",
        patrol_area_name="운반 맵 점검",
        path_json=path_json,
        is_enabled=False,
    )

    assert response["result_code"] == "UPDATED"
    assert response["patrol_area"]["map_id"] == "map_test12_0506"
    assert repository.calls == [
        ("get_map_profile", "map_test12_0506"),
        (
            "update_patrol_area",
            "map_test12_0506",
            "transport_patrol_test",
            3,
            "운반 맵 점검",
            path_json,
            False,
        ),
    ]


def test_update_patrol_area_path_rejects_frame_mismatch():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).update_patrol_area_path(
        patrol_area_id="patrol_ward_night_01",
        expected_revision=7,
        path_json={
            "header": {"frame_id": "odom"},
            "poses": [
                {"x": 0.0, "y": 0.0, "yaw": 0.0},
                {"x": 1.0, "y": 1.0, "yaw": 0.0},
            ],
        },
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "FRAME_ID_MISMATCH"
    assert response["patrol_area"] is None
    assert repository.calls == [("get_active_map_profile",)]


def test_update_patrol_area_path_rejects_path_with_too_few_poses():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).update_patrol_area_path(
        patrol_area_id="patrol_ward_night_01",
        expected_revision=7,
        path_json={
            "header": {"frame_id": "map"},
            "poses": [{"x": 0.0, "y": 0.0, "yaw": 0.0}],
        },
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "PATROL_PATH_TOO_SHORT"
    assert response["patrol_area"] is None


def test_update_patrol_area_path_rejects_invalid_pose_shape():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).update_patrol_area_path(
        patrol_area_id="patrol_ward_night_01",
        expected_revision=7,
        path_json={
            "header": {"frame_id": "map"},
            "poses": [
                {"x": 0.0, "y": 0.0, "yaw": 0.0},
                {"x": "bad", "y": 1.0, "yaw": 0.0},
            ],
        },
    )

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "PATROL_PATH_INVALID"
    assert response["patrol_area"] is None


def test_update_patrol_area_path_reports_revision_conflict():
    repository = FakeCoordinateConfigRepository()
    repository.patrol_area_update_result = {
        "status": "REVISION_CONFLICT",
        "patrol_area": repository.patrol_areas[0],
    }

    response = _service(repository).update_patrol_area_path(
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

    assert response["result_code"] == "CONFLICT"
    assert response["reason_code"] == "PATROL_AREA_REVISION_CONFLICT"
    assert response["patrol_area"] is None


def test_update_patrol_area_path_async_uses_async_repository_method():
    repository = FakeCoordinateConfigRepository()

    response = asyncio.run(
        _service(repository).async_update_patrol_area_path(
            patrol_area_id="patrol_ward_night_01",
            expected_revision="7",
            path_json={
                "header": {"frame_id": "map"},
                "poses": [
                    {"x": "0.0", "y": "0.0", "yaw": "0.0"},
                    {"x": "1.0", "y": "1.0", "yaw": "0.0"},
                ],
            },
        )
    )

    assert response["result_code"] == "UPDATED"
    assert response["patrol_area"]["revision"] == 8
    assert repository.calls == [
        ("async_get_active_map_profile",),
        (
            "async_update_patrol_area_path",
            "map_test11_0423",
            "patrol_ward_night_01",
            7,
            {
                "header": {"frame_id": "map"},
                "poses": [
                    {"x": 0.0, "y": 0.0, "yaw": 0.0},
                    {"x": 1.0, "y": 1.0, "yaw": 0.0},
                ],
            },
        ),
    ]


def test_get_map_asset_returns_active_map_yaml_text_with_hash(tmp_path):
    repository = FakeCoordinateConfigRepository()
    yaml_path = tmp_path / "map.yaml"
    yaml_text = "image: map.pgm\nresolution: 0.020\norigin: [0, 0, 0]\n"
    yaml_path.write_text(yaml_text, encoding="utf-8")
    repository.map_profile["yaml_path"] = str(yaml_path)

    response = _service(repository).get_map_asset(asset_type="yaml")

    assert response["result_code"] == "OK"
    assert response["reason_code"] is None
    assert response["map_id"] == "map_test11_0423"
    assert response["asset_type"] == "YAML"
    assert response["encoding"] == "TEXT"
    assert response["content_text"] == yaml_text
    assert response["content_base64"] is None
    assert response["size_bytes"] == len(yaml_text.encode("utf-8"))
    assert response["sha256"] == hashlib.sha256(yaml_text.encode("utf-8")).hexdigest()
    assert repository.calls == [("get_active_map_profile",)]


def test_get_map_asset_returns_requested_map_pgm_base64_with_hash(tmp_path):
    repository = FakeCoordinateConfigRepository()
    pgm_path = tmp_path / "map.pgm"
    pgm_bytes = b"P5\n2 1\n255\n\x00\xff"
    pgm_path.write_bytes(pgm_bytes)
    map_profile = dict(repository.map_profile)
    map_profile["map_id"] = "map_alt"
    map_profile["pgm_path"] = str(pgm_path)
    repository.map_profiles_by_id["map_alt"] = map_profile

    response = _service(repository).get_map_asset(
        map_id="map_alt",
        asset_type="PGM",
    )

    assert response["result_code"] == "OK"
    assert response["map_id"] == "map_alt"
    assert response["asset_type"] == "PGM"
    assert response["encoding"] == "BASE64"
    assert response["content_text"] is None
    assert response["content_base64"] == base64.b64encode(pgm_bytes).decode("ascii")
    assert response["size_bytes"] == len(pgm_bytes)
    assert response["sha256"] == hashlib.sha256(pgm_bytes).hexdigest()
    assert repository.calls == [("get_map_profile", "map_alt")]


def test_get_map_asset_rejects_invalid_asset_type_without_db_read():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).get_map_asset(asset_type="PNG")

    assert response["result_code"] == "INVALID_REQUEST"
    assert response["reason_code"] == "MAP_ASSET_REQUEST_INVALID"
    assert response["content_text"] is None
    assert response["content_base64"] is None
    assert repository.calls == []


def test_get_map_asset_reports_missing_requested_map():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).get_map_asset(
        map_id="missing_map",
        asset_type="YAML",
    )

    assert response["result_code"] == "NOT_FOUND"
    assert response["reason_code"] == "MAP_NOT_FOUND"
    assert response["map_id"] == "missing_map"
    assert repository.calls == [("get_map_profile", "missing_map")]


def test_get_map_asset_rejects_payload_too_large(tmp_path):
    repository = FakeCoordinateConfigRepository()
    yaml_path = tmp_path / "map.yaml"
    yaml_path.write_text("image: map.pgm\n", encoding="utf-8")
    repository.map_profile["yaml_path"] = str(yaml_path)

    service = CoordinateConfigService(
        repository=repository,
        clock=lambda: datetime(2026, 5, 2, 3, 10, 0, tzinfo=timezone.utc),
        map_asset_max_bytes=1,
    )

    response = service.get_map_asset(asset_type="YAML")

    assert response["result_code"] == "PAYLOAD_TOO_LARGE"
    assert response["reason_code"] == "MAP_ASSET_TOO_LARGE"
    assert response["size_bytes"] == len("image: map.pgm\n".encode("utf-8"))
    assert response["content_text"] is None
    assert response["content_base64"] is None


def test_get_map_asset_async_uses_async_repository_method(tmp_path):
    repository = FakeCoordinateConfigRepository()
    yaml_path = tmp_path / "map.yaml"
    yaml_path.write_text("image: map.pgm\n", encoding="utf-8")
    repository.map_profile["yaml_path"] = str(yaml_path)

    response = asyncio.run(
        _service(repository).async_get_map_asset(
            map_id="map_test11_0423",
            asset_type="YAML",
        )
    )

    assert response["result_code"] == "OK"
    assert response["encoding"] == "TEXT"
    assert repository.calls == [("async_get_map_profile", "map_test11_0423")]
