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
        self.existing_zone = None
        self.create_result = None
        self.update_result = None

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

    def get_operation_zone(self, *, zone_id):
        self.calls.append(("get_operation_zone", zone_id))
        return self.existing_zone

    async def async_get_operation_zone(self, *, zone_id):
        self.calls.append(("async_get_operation_zone", zone_id))
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
                "is_enabled": kwargs["is_enabled"],
                "created_at": datetime(2026, 5, 2, 12, 0, 0),
                "updated_at": datetime(2026, 5, 2, 12, 3, 0),
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
        "is_enabled": True,
        "created_at": "2026-05-02T12:02:00",
        "updated_at": "2026-05-02T12:02:00",
    }
    assert repository.calls == [
        ("get_active_map_profile",),
        ("get_operation_zone", "caregiver_room"),
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
        ("get_operation_zone", "room_301"),
    ]


def test_create_operation_zone_rejects_non_active_map_id():
    repository = FakeCoordinateConfigRepository()

    response = _service(repository).create_operation_zone(
        zone_id="caregiver_room",
        zone_name="보호사실",
        zone_type="STAFF_STATION",
        map_id="other_map",
    )

    assert response["result_code"] == "REJECTED"
    assert response["reason_code"] == "MAP_NOT_ACTIVE"
    assert response["operation_zone"] is None
    assert repository.calls == [("get_active_map_profile",)]


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
