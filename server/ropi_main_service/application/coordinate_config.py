import asyncio
import json
import re
from datetime import date, datetime, timezone

from server.ropi_main_service.persistence.repositories.coordinate_config_repository import (
    CoordinateConfigRepository,
)


ALLOWED_OPERATION_ZONE_TYPES = {
    "ROOM",
    "ENTRANCE",
    "CORRIDOR",
    "NURSE_STATION",
    "STAFF_STATION",
    "CAREGIVER_ROOM",
    "SUPPLY_STATION",
    "DOCK",
    "RESTRICTED",
    "OTHER",
}
ZONE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


class CoordinateConfigService:
    def __init__(self, repository=None, clock=None):
        self.repository = repository or CoordinateConfigRepository()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_active_map_bundle(
        self,
        *,
        include_disabled=True,
        include_patrol_paths=True,
    ):
        include_disabled = self._bool(include_disabled)
        include_patrol_paths = self._bool(include_patrol_paths)

        active_map = self.repository.get_active_map_profile()
        if not active_map:
            return self._not_found_response()

        map_profile = self._format_map_profile(active_map)
        map_id = map_profile["map_id"]
        operation_zones = self.repository.get_operation_zones(
            map_id=map_id,
            include_disabled=include_disabled,
        )
        goal_poses = self.repository.get_goal_poses(
            map_id=map_id,
            include_disabled=include_disabled,
        )
        patrol_areas = self.repository.get_patrol_areas(
            map_id=map_id,
            include_disabled=include_disabled,
        )

        return self._ok_response(
            map_profile=map_profile,
            operation_zones=operation_zones,
            goal_poses=goal_poses,
            patrol_areas=patrol_areas,
            include_patrol_paths=include_patrol_paths,
        )

    def create_operation_zone(
        self,
        *,
        zone_id,
        zone_name,
        zone_type,
        map_id=None,
        is_enabled=True,
    ):
        map_profile, error = self._resolve_active_map(map_id=map_id)
        if error:
            return error

        normalized, error = self._normalize_operation_zone_input(
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            is_enabled=is_enabled,
        )
        if error:
            return error

        existing_zone = self.repository.get_operation_zone(
            zone_id=normalized["zone_id"],
        )
        if existing_zone:
            return self._operation_zone_error(
                result_code="CONFLICT",
                reason_code="ZONE_ID_DUPLICATED",
                result_message="이미 존재하는 구역 ID입니다.",
            )

        try:
            row = self.repository.create_operation_zone(
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return self._operation_zone_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="구역 생성 중 DB 쓰기에 실패했습니다.",
            )

        return {
            "result_code": "CREATED",
            "result_message": None,
            "reason_code": None,
            "operation_zone": self._format_operation_zone(row or {}),
        }

    async def async_create_operation_zone(
        self,
        *,
        zone_id,
        zone_name,
        zone_type,
        map_id=None,
        is_enabled=True,
    ):
        map_profile, error = await self._async_resolve_active_map(map_id=map_id)
        if error:
            return error

        normalized, error = self._normalize_operation_zone_input(
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            is_enabled=is_enabled,
        )
        if error:
            return error

        existing_zone = await self._call_async_or_thread(
            "async_get_operation_zone",
            "get_operation_zone",
            zone_id=normalized["zone_id"],
        )
        if existing_zone:
            return self._operation_zone_error(
                result_code="CONFLICT",
                reason_code="ZONE_ID_DUPLICATED",
                result_message="이미 존재하는 구역 ID입니다.",
            )

        try:
            row = await self._call_async_or_thread(
                "async_create_operation_zone",
                "create_operation_zone",
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return self._operation_zone_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="구역 생성 중 DB 쓰기에 실패했습니다.",
            )

        return {
            "result_code": "CREATED",
            "result_message": None,
            "reason_code": None,
            "operation_zone": self._format_operation_zone(row or {}),
        }

    def update_operation_zone(
        self,
        *,
        zone_id,
        expected_revision,
        zone_name,
        zone_type,
        is_enabled,
    ):
        map_profile, error = self._resolve_active_map()
        if error:
            return error

        normalized, error = self._normalize_operation_zone_input(
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            is_enabled=is_enabled,
        )
        if error:
            return error

        revision = self._optional_int(expected_revision)
        if revision is None or revision < 1:
            return self._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_REVISION_CONFLICT",
                result_message="expected_revision이 유효하지 않습니다.",
            )

        try:
            result = self.repository.update_operation_zone(
                map_id=map_profile["map_id"],
                expected_revision=revision,
                **normalized,
            )
        except Exception:
            return self._operation_zone_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="구역 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_operation_zone_update_result(result)

    async def async_update_operation_zone(
        self,
        *,
        zone_id,
        expected_revision,
        zone_name,
        zone_type,
        is_enabled,
    ):
        map_profile, error = await self._async_resolve_active_map()
        if error:
            return error

        normalized, error = self._normalize_operation_zone_input(
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            is_enabled=is_enabled,
        )
        if error:
            return error

        revision = self._optional_int(expected_revision)
        if revision is None or revision < 1:
            return self._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_REVISION_CONFLICT",
                result_message="expected_revision이 유효하지 않습니다.",
            )

        try:
            result = await self._call_async_or_thread(
                "async_update_operation_zone",
                "update_operation_zone",
                map_id=map_profile["map_id"],
                expected_revision=revision,
                **normalized,
            )
        except Exception:
            return self._operation_zone_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="구역 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_operation_zone_update_result(result)

    async def async_get_active_map_bundle(
        self,
        *,
        include_disabled=True,
        include_patrol_paths=True,
    ):
        include_disabled = self._bool(include_disabled)
        include_patrol_paths = self._bool(include_patrol_paths)

        active_map = await self._call_async_or_thread(
            "async_get_active_map_profile",
            "get_active_map_profile",
        )
        if not active_map:
            return self._not_found_response()

        map_profile = self._format_map_profile(active_map)
        map_id = map_profile["map_id"]

        operation_zones, goal_poses, patrol_areas = await asyncio.gather(
            self._call_async_or_thread(
                "async_get_operation_zones",
                "get_operation_zones",
                map_id=map_id,
                include_disabled=include_disabled,
            ),
            self._call_async_or_thread(
                "async_get_goal_poses",
                "get_goal_poses",
                map_id=map_id,
                include_disabled=include_disabled,
            ),
            self._call_async_or_thread(
                "async_get_patrol_areas",
                "get_patrol_areas",
                map_id=map_id,
                include_disabled=include_disabled,
            ),
        )

        return self._ok_response(
            map_profile=map_profile,
            operation_zones=operation_zones,
            goal_poses=goal_poses,
            patrol_areas=patrol_areas,
            include_patrol_paths=include_patrol_paths,
        )

    async def _call_async_or_thread(self, async_name, sync_name, **kwargs):
        async_method = getattr(self.repository, async_name, None)
        if async_method is not None:
            return await async_method(**kwargs)

        sync_method = getattr(self.repository, sync_name)
        return await asyncio.to_thread(sync_method, **kwargs)

    def _resolve_active_map(self, *, map_id=None):
        active_map = self.repository.get_active_map_profile()
        return self._format_active_map_resolution(active_map, map_id=map_id)

    async def _async_resolve_active_map(self, *, map_id=None):
        active_map = await self._call_async_or_thread(
            "async_get_active_map_profile",
            "get_active_map_profile",
        )
        return self._format_active_map_resolution(active_map, map_id=map_id)

    def _format_active_map_resolution(self, active_map, *, map_id=None):
        if not active_map:
            return None, self._operation_zone_error(
                result_code="NOT_FOUND",
                reason_code="ACTIVE_MAP_NOT_FOUND",
                result_message="활성 map_profile이 없습니다.",
            )

        map_profile = self._format_map_profile(active_map)
        requested_map_id = self._normalize_optional_text(map_id)
        if requested_map_id and requested_map_id != map_profile["map_id"]:
            return None, self._operation_zone_error(
                result_code="REJECTED",
                reason_code="MAP_NOT_ACTIVE",
                result_message="phase 1에서는 active map만 수정할 수 있습니다.",
            )

        return map_profile, None

    def _ok_response(
        self,
        *,
        map_profile,
        operation_zones,
        goal_poses,
        patrol_areas,
        include_patrol_paths,
    ):
        return {
            "result_code": "OK",
            "result_message": None,
            "reason_code": None,
            "generated_at": self._generated_at(),
            "map_profile": map_profile,
            "operation_zones": [
                self._format_operation_zone(row) for row in operation_zones or []
            ],
            "goal_poses": [self._format_goal_pose(row) for row in goal_poses or []],
            "patrol_areas": [
                self._format_patrol_area(
                    row,
                    include_patrol_path=include_patrol_paths,
                )
                for row in patrol_areas or []
            ],
        }

    def _not_found_response(self):
        return {
            "result_code": "NOT_FOUND",
            "result_message": "활성 map_profile이 없습니다.",
            "reason_code": "ACTIVE_MAP_NOT_FOUND",
            "generated_at": self._generated_at(),
            "map_profile": None,
            "operation_zones": [],
            "goal_poses": [],
            "patrol_areas": [],
        }

    @classmethod
    def _format_operation_zone_update_result(cls, result):
        result = result if isinstance(result, dict) else {}
        status = result.get("status")
        if status == "UPDATED":
            return {
                "result_code": "UPDATED",
                "result_message": None,
                "reason_code": None,
                "operation_zone": cls._format_operation_zone(
                    result.get("operation_zone") or {}
                ),
            }
        if status == "NOT_FOUND":
            return cls._operation_zone_error(
                result_code="NOT_FOUND",
                reason_code="ZONE_NOT_FOUND",
                result_message="수정할 구역을 찾을 수 없습니다.",
            )
        if status == "REVISION_CONFLICT":
            return cls._operation_zone_error(
                result_code="CONFLICT",
                reason_code="ZONE_REVISION_CONFLICT",
                result_message="구역 revision이 최신 값과 일치하지 않습니다.",
            )
        return cls._operation_zone_error(
            result_code="UNAVAILABLE",
            reason_code="CONFIG_WRITE_FAILED",
            result_message="구역 수정 결과를 확인할 수 없습니다.",
        )

    @staticmethod
    def _operation_zone_error(*, result_code, reason_code, result_message):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "operation_zone": None,
        }

    @classmethod
    def _normalize_operation_zone_input(
        cls,
        *,
        zone_id,
        zone_name,
        zone_type,
        is_enabled,
    ):
        normalized_zone_id = cls._normalize_optional_text(zone_id)
        if (
            not normalized_zone_id
            or len(normalized_zone_id) > 100
            or not ZONE_ID_PATTERN.match(normalized_zone_id)
        ):
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_ID_INVALID",
                result_message="zone_id가 유효하지 않습니다.",
            )

        normalized_zone_name = cls._normalize_optional_text(zone_name)
        if not normalized_zone_name or len(normalized_zone_name) > 100:
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_NAME_INVALID",
                result_message="zone_name이 유효하지 않습니다.",
            )

        normalized_zone_type = cls._normalize_optional_text(zone_type)
        if normalized_zone_type:
            normalized_zone_type = normalized_zone_type.upper()
        if (
            not normalized_zone_type
            or len(normalized_zone_type) > 50
            or normalized_zone_type not in ALLOWED_OPERATION_ZONE_TYPES
        ):
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_TYPE_INVALID",
                result_message="zone_type이 유효하지 않습니다.",
            )

        return {
            "zone_id": normalized_zone_id,
            "zone_name": normalized_zone_name,
            "zone_type": normalized_zone_type,
            "is_enabled": cls._bool(is_enabled),
        }, None

    def _generated_at(self):
        value = self._clock()
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @classmethod
    def _format_map_profile(cls, row):
        return {
            "map_id": row.get("map_id"),
            "map_name": row.get("map_name"),
            "map_revision": cls._optional_int(row.get("map_revision")) or 0,
            "frame_id": row.get("frame_id") or "map",
            "yaml_path": row.get("yaml_path"),
            "pgm_path": row.get("pgm_path"),
            "is_active": cls._bool(row.get("is_active")),
        }

    @classmethod
    def _format_operation_zone(cls, row):
        return {
            "zone_id": row.get("zone_id"),
            "map_id": row.get("map_id"),
            "zone_name": row.get("zone_name"),
            "zone_type": row.get("zone_type"),
            "revision": cls._optional_int(row.get("revision")) or 0,
            "is_enabled": cls._bool(row.get("is_enabled")),
            "created_at": cls._isoformat(row.get("created_at")),
            "updated_at": cls._isoformat(row.get("updated_at")),
        }

    @classmethod
    def _format_goal_pose(cls, row):
        return {
            "goal_pose_id": row.get("goal_pose_id"),
            "map_id": row.get("map_id"),
            "zone_id": row.get("zone_id"),
            "zone_name": row.get("zone_name"),
            "purpose": row.get("purpose"),
            "pose_x": cls._optional_float(row.get("pose_x")) or 0.0,
            "pose_y": cls._optional_float(row.get("pose_y")) or 0.0,
            "pose_yaw": cls._optional_float(row.get("pose_yaw")) or 0.0,
            "frame_id": row.get("frame_id") or "map",
            "is_enabled": cls._bool(row.get("is_enabled")),
            "created_at": cls._isoformat(row.get("created_at")),
            "updated_at": cls._isoformat(row.get("updated_at")),
        }

    @classmethod
    def _format_patrol_area(cls, row, *, include_patrol_path):
        path_json = cls._json_object(row.get("path_json"))
        poses = path_json.get("poses")
        if not isinstance(poses, list):
            poses = []

        header = (
            path_json.get("header")
            if isinstance(path_json.get("header"), dict)
            else {}
        )
        waypoint_count = cls._optional_int(row.get("waypoint_count"))
        if waypoint_count is None:
            waypoint_count = len(poses)

        return {
            "patrol_area_id": row.get("patrol_area_id"),
            "map_id": row.get("map_id"),
            "patrol_area_name": row.get("patrol_area_name"),
            "revision": cls._optional_int(row.get("revision")) or 0,
            "path_json": path_json if include_patrol_path else None,
            "waypoint_count": waypoint_count,
            "path_frame_id": row.get("path_frame_id") or header.get("frame_id"),
            "is_enabled": cls._bool(row.get("is_enabled")),
            "created_at": cls._isoformat(row.get("created_at")),
            "updated_at": cls._isoformat(row.get("updated_at")),
        }

    @staticmethod
    def _json_object(value):
        if isinstance(value, dict):
            return value
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return loaded if isinstance(loaded, dict) else {}
        return {}

    @staticmethod
    def _bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        text = str(value or "").strip().lower()
        if text in {"1", "true", "yes", "y"}:
            return True
        if text in {"0", "false", "no", "n", ""}:
            return False
        return bool(value)

    @staticmethod
    def _optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_float(value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_optional_text(value):
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _isoformat(value):
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)


__all__ = ["CoordinateConfigService"]
