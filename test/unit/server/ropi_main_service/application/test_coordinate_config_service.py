import asyncio
import json
from datetime import datetime, timezone

from server.ropi_main_service.application.coordinate_config import (
    CoordinateConfigService,
)


class FakeCoordinateConfigRepository:
    def __init__(self):
        self.calls = []
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
        self.operation_zones = [
            {
                "zone_id": "room_301",
                "map_id": "map_test11_0423",
                "zone_name": "301호",
                "zone_type": "ROOM",
                "revision": "2",
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

    def get_active_map_profile(self):
        self.calls.append(("get_active_map_profile",))
        return self.map_profile

    async def async_get_active_map_profile(self):
        self.calls.append(("async_get_active_map_profile",))
        return self.map_profile

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

    def get_patrol_areas(self, *, map_id, include_disabled=True):
        self.calls.append(("get_patrol_areas", map_id, include_disabled))
        return self.patrol_areas

    async def async_get_patrol_areas(self, *, map_id, include_disabled=True):
        self.calls.append(("async_get_patrol_areas", map_id, include_disabled))
        return self.patrol_areas


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
    assert repository.calls == [("get_active_map_profile",)]


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
    ]
