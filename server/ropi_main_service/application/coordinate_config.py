import asyncio
import re
from datetime import datetime, timezone

from server.ropi_main_service.application.coordinate_config_assets import MapAssetReader
from server.ropi_main_service.application.coordinate_config_formatters import (
    bool_value,
    format_goal_pose,
    format_map_profile,
    format_operation_zone,
    format_patrol_area,
    generated_at,
    json_object,
    normalize_optional_text,
    optional_float,
    optional_int,
)
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
ALLOWED_GOAL_POSE_PURPOSES = {"PICKUP", "DESTINATION", "DOCK"}
ZONE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


class CoordinateConfigService:
    def __init__(self, repository=None, clock=None, map_asset_max_bytes=None):
        self.repository = repository or CoordinateConfigRepository()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.map_asset_reader = MapAssetReader(max_bytes=map_asset_max_bytes)
        self.map_asset_max_bytes = self.map_asset_reader.max_bytes

    def get_active_map_bundle(
        self,
        *,
        include_disabled=True,
        include_zone_boundaries=True,
        include_patrol_paths=True,
    ):
        include_disabled = bool_value(include_disabled)
        include_zone_boundaries = bool_value(include_zone_boundaries)
        include_patrol_paths = bool_value(include_patrol_paths)

        active_map = self.repository.get_active_map_profile()
        if not active_map:
            return self._not_found_response()

        map_profile = format_map_profile(active_map)
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
            include_zone_boundaries=include_zone_boundaries,
            include_patrol_paths=include_patrol_paths,
        )

    def get_map_asset(
        self,
        *,
        asset_type,
        map_id=None,
        encoding=None,
    ):
        request, error = self.map_asset_reader.normalize_request(
            asset_type=asset_type,
            encoding=encoding,
        )
        if error:
            return error

        map_profile, error = self._resolve_map_profile_for_asset(
            map_id=map_id,
        )
        if error:
            return error

        return self.map_asset_reader.read(
            map_profile,
            asset_type=request["asset_type"],
            encoding=request["encoding"],
        )

    async def async_get_map_asset(
        self,
        *,
        asset_type,
        map_id=None,
        encoding=None,
    ):
        request, error = self.map_asset_reader.normalize_request(
            asset_type=asset_type,
            encoding=encoding,
        )
        if error:
            return error

        map_profile, error = await self._async_resolve_map_profile_for_asset(
            map_id=map_id,
        )
        if error:
            return error

        return await asyncio.to_thread(
            self.map_asset_reader.read,
            map_profile,
            asset_type=request["asset_type"],
            encoding=request["encoding"],
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
            "operation_zone": format_operation_zone(row or {}),
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
            "operation_zone": format_operation_zone(row or {}),
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

        revision = optional_int(expected_revision)
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

        revision = optional_int(expected_revision)
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

    def update_operation_zone_boundary(
        self,
        *,
        zone_id,
        expected_revision,
        boundary_json,
    ):
        map_profile, error = self._resolve_active_map()
        if error:
            return error

        normalized, error = self._normalize_operation_zone_boundary_input(
            zone_id=zone_id,
            expected_revision=expected_revision,
            boundary_json=boundary_json,
            active_frame_id=map_profile["frame_id"],
        )
        if error:
            return error

        try:
            result = self.repository.update_operation_zone_boundary(
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return self._operation_zone_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="구역 boundary 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_operation_zone_update_result(result)

    async def async_update_operation_zone_boundary(
        self,
        *,
        zone_id,
        expected_revision,
        boundary_json,
    ):
        map_profile, error = await self._async_resolve_active_map()
        if error:
            return error

        normalized, error = self._normalize_operation_zone_boundary_input(
            zone_id=zone_id,
            expected_revision=expected_revision,
            boundary_json=boundary_json,
            active_frame_id=map_profile["frame_id"],
        )
        if error:
            return error

        try:
            result = await self._call_async_or_thread(
                "async_update_operation_zone_boundary",
                "update_operation_zone_boundary",
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return self._operation_zone_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="구역 boundary 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_operation_zone_update_result(result)

    def update_goal_pose(
        self,
        *,
        goal_pose_id,
        expected_updated_at=None,
        zone_id=None,
        purpose,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        is_enabled,
    ):
        map_profile, error = self._resolve_active_map(
            error_factory=self._goal_pose_error,
        )
        if error:
            return error

        normalized, error = self._normalize_goal_pose_input(
            goal_pose_id=goal_pose_id,
            expected_updated_at=expected_updated_at,
            zone_id=zone_id,
            purpose=purpose,
            pose_x=pose_x,
            pose_y=pose_y,
            pose_yaw=pose_yaw,
            frame_id=frame_id,
            is_enabled=is_enabled,
            active_frame_id=map_profile["frame_id"],
        )
        if error:
            return error

        zone_error = self._validate_goal_pose_zone(
            map_id=map_profile["map_id"],
            zone_id=normalized["zone_id"],
        )
        if zone_error:
            return zone_error

        try:
            result = self.repository.update_goal_pose(
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return self._goal_pose_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="목적지 좌표 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_goal_pose_update_result(result)

    async def async_update_goal_pose(
        self,
        *,
        goal_pose_id,
        expected_updated_at=None,
        zone_id=None,
        purpose,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        is_enabled,
    ):
        map_profile, error = await self._async_resolve_active_map(
            error_factory=self._goal_pose_error,
        )
        if error:
            return error

        normalized, error = self._normalize_goal_pose_input(
            goal_pose_id=goal_pose_id,
            expected_updated_at=expected_updated_at,
            zone_id=zone_id,
            purpose=purpose,
            pose_x=pose_x,
            pose_y=pose_y,
            pose_yaw=pose_yaw,
            frame_id=frame_id,
            is_enabled=is_enabled,
            active_frame_id=map_profile["frame_id"],
        )
        if error:
            return error

        zone_error = await self._async_validate_goal_pose_zone(
            map_id=map_profile["map_id"],
            zone_id=normalized["zone_id"],
        )
        if zone_error:
            return zone_error

        try:
            result = await self._call_async_or_thread(
                "async_update_goal_pose",
                "update_goal_pose",
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return self._goal_pose_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="목적지 좌표 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_goal_pose_update_result(result)

    def update_patrol_area_path(
        self,
        *,
        patrol_area_id,
        expected_revision,
        path_json,
    ):
        map_profile, error = self._resolve_active_map(
            error_factory=self._patrol_area_error,
        )
        if error:
            return error

        normalized, error = self._normalize_patrol_area_path_input(
            patrol_area_id=patrol_area_id,
            expected_revision=expected_revision,
            path_json=path_json,
            active_frame_id=map_profile["frame_id"],
        )
        if error:
            return error

        try:
            result = self.repository.update_patrol_area_path(
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return self._patrol_area_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="순찰 경로 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_patrol_area_update_result(result)

    async def async_update_patrol_area_path(
        self,
        *,
        patrol_area_id,
        expected_revision,
        path_json,
    ):
        map_profile, error = await self._async_resolve_active_map(
            error_factory=self._patrol_area_error,
        )
        if error:
            return error

        normalized, error = self._normalize_patrol_area_path_input(
            patrol_area_id=patrol_area_id,
            expected_revision=expected_revision,
            path_json=path_json,
            active_frame_id=map_profile["frame_id"],
        )
        if error:
            return error

        try:
            result = await self._call_async_or_thread(
                "async_update_patrol_area_path",
                "update_patrol_area_path",
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return self._patrol_area_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="순찰 경로 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_patrol_area_update_result(result)

    async def async_get_active_map_bundle(
        self,
        *,
        include_disabled=True,
        include_zone_boundaries=True,
        include_patrol_paths=True,
    ):
        include_disabled = bool_value(include_disabled)
        include_zone_boundaries = bool_value(include_zone_boundaries)
        include_patrol_paths = bool_value(include_patrol_paths)

        active_map = await self._call_async_or_thread(
            "async_get_active_map_profile",
            "get_active_map_profile",
        )
        if not active_map:
            return self._not_found_response()

        map_profile = format_map_profile(active_map)
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
            include_zone_boundaries=include_zone_boundaries,
            include_patrol_paths=include_patrol_paths,
        )

    async def _call_async_or_thread(self, async_name, sync_name, **kwargs):
        async_method = getattr(self.repository, async_name, None)
        if async_method is not None:
            return await async_method(**kwargs)

        sync_method = getattr(self.repository, sync_name)
        return await asyncio.to_thread(sync_method, **kwargs)

    def _resolve_active_map(self, *, map_id=None, error_factory=None):
        active_map = self.repository.get_active_map_profile()
        return self._format_active_map_resolution(
            active_map,
            map_id=map_id,
            error_factory=error_factory,
        )

    async def _async_resolve_active_map(self, *, map_id=None, error_factory=None):
        active_map = await self._call_async_or_thread(
            "async_get_active_map_profile",
            "get_active_map_profile",
        )
        return self._format_active_map_resolution(
            active_map,
            map_id=map_id,
            error_factory=error_factory,
        )

    def _format_active_map_resolution(self, active_map, *, map_id=None, error_factory=None):
        error_factory = error_factory or self._operation_zone_error
        if not active_map:
            return None, error_factory(
                result_code="NOT_FOUND",
                reason_code="ACTIVE_MAP_NOT_FOUND",
                result_message="활성 map_profile이 없습니다.",
            )

        map_profile = format_map_profile(active_map)
        requested_map_id = normalize_optional_text(map_id)
        if requested_map_id and requested_map_id != map_profile["map_id"]:
            return None, error_factory(
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
        include_zone_boundaries,
        include_patrol_paths,
    ):
        return {
            "result_code": "OK",
            "result_message": None,
            "reason_code": None,
            "generated_at": generated_at(self._clock),
            "map_profile": map_profile,
            "operation_zones": [
                format_operation_zone(
                    row,
                    include_boundary=include_zone_boundaries,
                )
                for row in operation_zones or []
            ],
            "goal_poses": [format_goal_pose(row) for row in goal_poses or []],
            "patrol_areas": [
                format_patrol_area(
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
            "generated_at": generated_at(self._clock),
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
                "operation_zone": format_operation_zone(
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

    @classmethod
    def _format_goal_pose_update_result(cls, result):
        result = result if isinstance(result, dict) else {}
        status = result.get("status")
        if status == "UPDATED":
            return {
                "result_code": "UPDATED",
                "result_message": None,
                "reason_code": None,
                "goal_pose": format_goal_pose(result.get("goal_pose") or {}),
            }
        if status == "NOT_FOUND":
            return cls._goal_pose_error(
                result_code="NOT_FOUND",
                reason_code="GOAL_POSE_NOT_FOUND",
                result_message="수정할 목적지 좌표를 찾을 수 없습니다.",
            )
        if status == "STALE":
            return cls._goal_pose_error(
                result_code="CONFLICT",
                reason_code="GOAL_POSE_STALE",
                result_message="목적지 좌표가 최신 값과 일치하지 않습니다.",
            )
        return cls._goal_pose_error(
            result_code="UNAVAILABLE",
            reason_code="CONFIG_WRITE_FAILED",
            result_message="목적지 좌표 수정 결과를 확인할 수 없습니다.",
        )

    @classmethod
    def _format_patrol_area_update_result(cls, result):
        result = result if isinstance(result, dict) else {}
        status = result.get("status")
        if status == "UPDATED":
            return {
                "result_code": "UPDATED",
                "result_message": None,
                "reason_code": None,
                "patrol_area": format_patrol_area(
                    result.get("patrol_area") or {},
                    include_patrol_path=True,
                ),
            }
        if status == "NOT_FOUND":
            return cls._patrol_area_error(
                result_code="NOT_FOUND",
                reason_code="PATROL_AREA_NOT_FOUND",
                result_message="수정할 순찰 구역을 찾을 수 없습니다.",
            )
        if status == "REVISION_CONFLICT":
            return cls._patrol_area_error(
                result_code="CONFLICT",
                reason_code="PATROL_AREA_REVISION_CONFLICT",
                result_message="순찰 경로 revision이 최신 값과 일치하지 않습니다.",
            )
        return cls._patrol_area_error(
            result_code="UNAVAILABLE",
            reason_code="CONFIG_WRITE_FAILED",
            result_message="순찰 경로 수정 결과를 확인할 수 없습니다.",
        )

    def _resolve_map_profile_for_asset(self, *, map_id):
        requested_map_id = normalize_optional_text(map_id)
        if requested_map_id:
            map_profile = self.repository.get_map_profile(map_id=requested_map_id)
            if not map_profile:
                return None, MapAssetReader._error(
                    result_code="NOT_FOUND",
                    reason_code="MAP_NOT_FOUND",
                    result_message="요청한 map_id를 찾을 수 없습니다.",
                    map_id=requested_map_id,
                )
            return map_profile, None

        map_profile = self.repository.get_active_map_profile()
        if not map_profile:
            return None, MapAssetReader._error(
                result_code="NOT_FOUND",
                reason_code="ACTIVE_MAP_NOT_FOUND",
                result_message="활성 map_profile이 없습니다.",
            )
        return map_profile, None

    async def _async_resolve_map_profile_for_asset(self, *, map_id):
        requested_map_id = normalize_optional_text(map_id)
        if requested_map_id:
            map_profile = await self._call_async_or_thread(
                "async_get_map_profile",
                "get_map_profile",
                map_id=requested_map_id,
            )
            if not map_profile:
                return None, MapAssetReader._error(
                    result_code="NOT_FOUND",
                    reason_code="MAP_NOT_FOUND",
                    result_message="요청한 map_id를 찾을 수 없습니다.",
                    map_id=requested_map_id,
                )
            return map_profile, None

        map_profile = await self._call_async_or_thread(
            "async_get_active_map_profile",
            "get_active_map_profile",
        )
        if not map_profile:
            return None, MapAssetReader._error(
                result_code="NOT_FOUND",
                reason_code="ACTIVE_MAP_NOT_FOUND",
                result_message="활성 map_profile이 없습니다.",
            )
        return map_profile, None

    @staticmethod
    def _operation_zone_error(*, result_code, reason_code, result_message):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "operation_zone": None,
        }

    @staticmethod
    def _goal_pose_error(*, result_code, reason_code, result_message):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "goal_pose": None,
        }

    @staticmethod
    def _patrol_area_error(*, result_code, reason_code, result_message):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "patrol_area": None,
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
        normalized_zone_id = normalize_optional_text(zone_id)
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

        normalized_zone_name = normalize_optional_text(zone_name)
        if not normalized_zone_name or len(normalized_zone_name) > 100:
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_NAME_INVALID",
                result_message="zone_name이 유효하지 않습니다.",
            )

        normalized_zone_type = normalize_optional_text(zone_type)
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
            "is_enabled": bool_value(is_enabled),
        }, None

    @classmethod
    def _normalize_operation_zone_boundary_input(
        cls,
        *,
        zone_id,
        expected_revision,
        boundary_json,
        active_frame_id,
    ):
        normalized_zone_id = normalize_optional_text(zone_id)
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

        revision = optional_int(expected_revision)
        if revision is None or revision < 1:
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_REVISION_CONFLICT",
                result_message="expected_revision이 유효하지 않습니다.",
            )

        if boundary_json is None:
            return {
                "zone_id": normalized_zone_id,
                "expected_revision": revision,
                "boundary_json": None,
            }, None

        boundary = json_object(boundary_json)
        if not boundary:
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_BOUNDARY_INVALID",
                result_message="boundary_json shape이 유효하지 않습니다.",
            )

        boundary_type = normalize_optional_text(boundary.get("type"))
        if boundary_type:
            boundary_type = boundary_type.upper()
        if boundary_type != "POLYGON":
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_BOUNDARY_INVALID",
                result_message="boundary_json.type은 POLYGON이어야 합니다.",
            )

        header = boundary.get("header")
        if not isinstance(header, dict):
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_BOUNDARY_INVALID",
                result_message="boundary_json.header가 유효하지 않습니다.",
            )

        frame_id = normalize_optional_text(header.get("frame_id"))
        if not frame_id:
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_BOUNDARY_INVALID",
                result_message="boundary_json.header.frame_id가 유효하지 않습니다.",
            )
        if frame_id != active_frame_id:
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="FRAME_ID_MISMATCH",
                result_message="구역 boundary frame_id가 active map frame과 일치하지 않습니다.",
            )

        raw_vertices = boundary.get("vertices")
        if not isinstance(raw_vertices, list):
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_BOUNDARY_INVALID",
                result_message="boundary_json.vertices가 유효하지 않습니다.",
            )
        if len(raw_vertices) < 3:
            return None, cls._operation_zone_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_BOUNDARY_TOO_SHORT",
                result_message="구역 boundary는 최소 세 개 이상의 꼭짓점이 필요합니다.",
            )

        vertices = []
        for vertex in raw_vertices:
            if not isinstance(vertex, dict):
                return None, cls._operation_zone_error(
                    result_code="INVALID_REQUEST",
                    reason_code="ZONE_BOUNDARY_INVALID",
                    result_message="구역 boundary 꼭짓점 shape이 유효하지 않습니다.",
                )
            x = optional_float(vertex.get("x"))
            y = optional_float(vertex.get("y"))
            if x is None or y is None:
                return None, cls._operation_zone_error(
                    result_code="INVALID_REQUEST",
                    reason_code="ZONE_BOUNDARY_INVALID",
                    result_message="구역 boundary 좌표가 유효하지 않습니다.",
                )
            vertices.append({"x": x, "y": y})

        return {
            "zone_id": normalized_zone_id,
            "expected_revision": revision,
            "boundary_json": {
                "type": "POLYGON",
                "header": {"frame_id": frame_id},
                "vertices": vertices,
            },
        }, None

    @classmethod
    def _normalize_goal_pose_input(
        cls,
        *,
        goal_pose_id,
        expected_updated_at,
        zone_id,
        purpose,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        is_enabled,
        active_frame_id,
    ):
        normalized_goal_pose_id = normalize_optional_text(goal_pose_id)
        if (
            not normalized_goal_pose_id
            or len(normalized_goal_pose_id) > 100
            or not ZONE_ID_PATTERN.match(normalized_goal_pose_id)
        ):
            return None, cls._goal_pose_error(
                result_code="INVALID_REQUEST",
                reason_code="GOAL_POSE_NOT_FOUND",
                result_message="goal_pose_id가 유효하지 않습니다.",
            )

        normalized_purpose = normalize_optional_text(purpose)
        if normalized_purpose:
            normalized_purpose = normalized_purpose.upper()
        if normalized_purpose not in ALLOWED_GOAL_POSE_PURPOSES:
            return None, cls._goal_pose_error(
                result_code="INVALID_REQUEST",
                reason_code="GOAL_POSE_PURPOSE_INVALID",
                result_message="purpose가 유효하지 않습니다.",
            )

        normalized_frame_id = normalize_optional_text(frame_id)
        if normalized_frame_id != active_frame_id:
            return None, cls._goal_pose_error(
                result_code="INVALID_REQUEST",
                reason_code="FRAME_ID_MISMATCH",
                result_message="frame_id가 active map frame과 일치하지 않습니다.",
            )

        parsed_pose_x = optional_float(pose_x)
        parsed_pose_y = optional_float(pose_y)
        parsed_pose_yaw = optional_float(pose_yaw)
        if parsed_pose_x is None or parsed_pose_y is None or parsed_pose_yaw is None:
            return None, cls._goal_pose_error(
                result_code="INVALID_REQUEST",
                reason_code="COORDINATE_OUT_OF_MAP_BOUNDS",
                result_message="좌표 값이 유효하지 않습니다.",
            )

        normalized_zone_id = normalize_optional_text(zone_id)
        if normalized_zone_id and (
            len(normalized_zone_id) > 100
            or not ZONE_ID_PATTERN.match(normalized_zone_id)
        ):
            return None, cls._goal_pose_error(
                result_code="INVALID_REQUEST",
                reason_code="ZONE_ID_INVALID",
                result_message="zone_id가 유효하지 않습니다.",
            )

        return {
            "goal_pose_id": normalized_goal_pose_id,
            "expected_updated_at": normalize_optional_text(expected_updated_at),
            "zone_id": normalized_zone_id,
            "purpose": normalized_purpose,
            "pose_x": parsed_pose_x,
            "pose_y": parsed_pose_y,
            "pose_yaw": parsed_pose_yaw,
            "frame_id": normalized_frame_id,
            "is_enabled": bool_value(is_enabled),
        }, None

    def _validate_goal_pose_zone(self, *, map_id, zone_id):
        if zone_id is None:
            return None

        zone = self.repository.get_operation_zone(zone_id=zone_id)
        return self._format_goal_pose_zone_validation(
            map_id=map_id,
            zone=zone,
        )

    async def _async_validate_goal_pose_zone(self, *, map_id, zone_id):
        if zone_id is None:
            return None

        zone = await self._call_async_or_thread(
            "async_get_operation_zone",
            "get_operation_zone",
            zone_id=zone_id,
        )
        return self._format_goal_pose_zone_validation(
            map_id=map_id,
            zone=zone,
        )

    @classmethod
    def _format_goal_pose_zone_validation(cls, *, map_id, zone):
        if not zone or zone.get("map_id") != map_id:
            return cls._goal_pose_error(
                result_code="NOT_FOUND",
                reason_code="ZONE_NOT_FOUND",
                result_message="연결할 구역을 찾을 수 없습니다.",
            )
        return None

    @classmethod
    def _normalize_patrol_area_path_input(
        cls,
        *,
        patrol_area_id,
        expected_revision,
        path_json,
        active_frame_id,
    ):
        normalized_patrol_area_id = normalize_optional_text(patrol_area_id)
        if (
            not normalized_patrol_area_id
            or len(normalized_patrol_area_id) > 100
            or not ZONE_ID_PATTERN.match(normalized_patrol_area_id)
        ):
            return None, cls._patrol_area_error(
                result_code="INVALID_REQUEST",
                reason_code="PATROL_AREA_NOT_FOUND",
                result_message="patrol_area_id가 유효하지 않습니다.",
            )

        revision = optional_int(expected_revision)
        if revision is None or revision < 1:
            return None, cls._patrol_area_error(
                result_code="INVALID_REQUEST",
                reason_code="PATROL_AREA_REVISION_CONFLICT",
                result_message="expected_revision이 유효하지 않습니다.",
            )

        path = json_object(path_json)
        header = path.get("header")
        if not isinstance(header, dict):
            return None, cls._patrol_area_error(
                result_code="INVALID_REQUEST",
                reason_code="PATROL_PATH_INVALID",
                result_message="path_json.header가 유효하지 않습니다.",
            )

        frame_id = normalize_optional_text(header.get("frame_id"))
        if frame_id != active_frame_id:
            return None, cls._patrol_area_error(
                result_code="INVALID_REQUEST",
                reason_code="FRAME_ID_MISMATCH",
                result_message="순찰 경로 frame_id가 active map frame과 일치하지 않습니다.",
            )

        raw_poses = path.get("poses")
        if not isinstance(raw_poses, list):
            return None, cls._patrol_area_error(
                result_code="INVALID_REQUEST",
                reason_code="PATROL_PATH_INVALID",
                result_message="path_json.poses가 유효하지 않습니다.",
            )
        if len(raw_poses) < 2:
            return None, cls._patrol_area_error(
                result_code="INVALID_REQUEST",
                reason_code="PATROL_PATH_TOO_SHORT",
                result_message="순찰 경로는 최소 두 개 이상의 waypoint가 필요합니다.",
            )

        poses = []
        for pose in raw_poses:
            if not isinstance(pose, dict):
                return None, cls._patrol_area_error(
                    result_code="INVALID_REQUEST",
                    reason_code="PATROL_PATH_INVALID",
                    result_message="순찰 waypoint shape이 유효하지 않습니다.",
                )
            x = optional_float(pose.get("x"))
            y = optional_float(pose.get("y"))
            yaw = optional_float(pose.get("yaw"))
            if x is None or y is None or yaw is None:
                return None, cls._patrol_area_error(
                    result_code="INVALID_REQUEST",
                    reason_code="PATROL_PATH_INVALID",
                    result_message="순찰 waypoint 좌표가 유효하지 않습니다.",
                )
            poses.append({"x": x, "y": y, "yaw": yaw})

        return {
            "patrol_area_id": normalized_patrol_area_id,
            "expected_revision": revision,
            "path_json": {
                "header": {"frame_id": frame_id},
                "poses": poses,
            },
        }, None

__all__ = ["CoordinateConfigService"]
