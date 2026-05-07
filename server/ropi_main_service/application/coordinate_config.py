import asyncio
from datetime import datetime, timezone

from server.ropi_main_service.application.coordinate_config_assets import MapAssetReader
from server.ropi_main_service.application.coordinate_config_formatters import (
    bool_value,
    format_goal_pose,
    format_map_profile,
    format_operation_zone,
    format_patrol_area,
    generated_at,
    normalize_optional_text,
    optional_int,
)
from server.ropi_main_service.application.coordinate_config_validators import (
    goal_pose_error,
    normalize_goal_pose_input,
    normalize_operation_zone_boundary_input,
    normalize_operation_zone_input,
    normalize_patrol_area_input,
    normalize_patrol_area_path_input,
    operation_zone_error,
    patrol_area_error,
)
from server.ropi_main_service.persistence.repositories.coordinate_config_repository import (
    CoordinateConfigRepository,
)


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
        return self.get_map_bundle(
            map_id=None,
            include_disabled=include_disabled,
            include_zone_boundaries=include_zone_boundaries,
            include_patrol_paths=include_patrol_paths,
        )

    def get_map_bundle(
        self,
        *,
        map_id=None,
        include_disabled=True,
        include_zone_boundaries=True,
        include_patrol_paths=True,
    ):
        include_disabled = bool_value(include_disabled)
        include_zone_boundaries = bool_value(include_zone_boundaries)
        include_patrol_paths = bool_value(include_patrol_paths)

        map_profile, error = self._resolve_map_profile(map_id=map_id)
        if error:
            return self._not_found_response(
                result_code=error.get("result_code", "NOT_FOUND"),
                reason_code=error.get("reason_code", "ACTIVE_MAP_NOT_FOUND"),
                result_message=error.get("result_message", "활성 map_profile이 없습니다."),
            )

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

        normalized, error = normalize_operation_zone_input(
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            is_enabled=is_enabled,
        )
        if error:
            return error

        existing_zone = self.repository.get_operation_zone(
            map_id=map_profile["map_id"],
            zone_id=normalized["zone_id"],
        )
        if existing_zone:
            return operation_zone_error(
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
            return operation_zone_error(
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

        normalized, error = normalize_operation_zone_input(
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
            map_id=map_profile["map_id"],
            zone_id=normalized["zone_id"],
        )
        if existing_zone:
            return operation_zone_error(
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
            return operation_zone_error(
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
        map_id=None,
    ):
        map_profile, error = self._resolve_map_profile(map_id=map_id)
        if error:
            return error

        normalized, error = normalize_operation_zone_input(
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            is_enabled=is_enabled,
        )
        if error:
            return error

        revision = optional_int(expected_revision)
        if revision is None or revision < 1:
            return operation_zone_error(
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
            return operation_zone_error(
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
        map_id=None,
    ):
        map_profile, error = await self._async_resolve_map_profile(map_id=map_id)
        if error:
            return error

        normalized, error = normalize_operation_zone_input(
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            is_enabled=is_enabled,
        )
        if error:
            return error

        revision = optional_int(expected_revision)
        if revision is None or revision < 1:
            return operation_zone_error(
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
            return operation_zone_error(
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
        map_id=None,
    ):
        map_profile, error = self._resolve_map_profile(map_id=map_id)
        if error:
            return error

        normalized, error = normalize_operation_zone_boundary_input(
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
            return operation_zone_error(
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
        map_id=None,
    ):
        map_profile, error = await self._async_resolve_map_profile(map_id=map_id)
        if error:
            return error

        normalized, error = normalize_operation_zone_boundary_input(
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
            return operation_zone_error(
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
        map_id=None,
    ):
        map_profile, error = self._resolve_map_profile(
            map_id=map_id,
            error_factory=goal_pose_error,
        )
        if error:
            return error

        normalized, error = normalize_goal_pose_input(
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
            return goal_pose_error(
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
        map_id=None,
    ):
        map_profile, error = await self._async_resolve_map_profile(
            map_id=map_id,
            error_factory=goal_pose_error,
        )
        if error:
            return error

        normalized, error = normalize_goal_pose_input(
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
            return goal_pose_error(
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
        map_id=None,
    ):
        map_profile, error = self._resolve_map_profile(
            map_id=map_id,
            error_factory=patrol_area_error,
        )
        if error:
            return error

        normalized, error = normalize_patrol_area_path_input(
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
            return patrol_area_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="순찰 경로 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_patrol_area_update_result(result)

    def create_patrol_area(
        self,
        *,
        patrol_area_id,
        patrol_area_name,
        path_json,
        map_id=None,
        is_enabled=True,
    ):
        map_profile, error = self._resolve_active_map(
            map_id=map_id,
            error_factory=patrol_area_error,
        )
        if error:
            return error

        normalized, error = normalize_patrol_area_input(
            patrol_area_id=patrol_area_id,
            patrol_area_name=patrol_area_name,
            path_json=path_json,
            active_frame_id=map_profile["frame_id"],
            is_enabled=is_enabled,
        )
        if error:
            return error

        existing_patrol_area = self.repository.get_patrol_area(
            patrol_area_id=normalized["patrol_area_id"],
        )
        if existing_patrol_area:
            return patrol_area_error(
                result_code="CONFLICT",
                reason_code="PATROL_AREA_ID_DUPLICATED",
                result_message="이미 존재하는 순찰 구역 ID입니다.",
            )

        try:
            row = self.repository.create_patrol_area(
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return patrol_area_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="순찰 구역 생성 중 DB 쓰기에 실패했습니다.",
            )

        return {
            "result_code": "CREATED",
            "result_message": None,
            "reason_code": None,
            "patrol_area": format_patrol_area(
                row or {},
                include_patrol_path=True,
            ),
        }

    def update_patrol_area(
        self,
        *,
        patrol_area_id,
        expected_revision,
        patrol_area_name,
        path_json,
        is_enabled,
    ):
        map_profile, error = self._resolve_active_map(
            error_factory=patrol_area_error,
        )
        if error:
            return error

        normalized, error = normalize_patrol_area_input(
            patrol_area_id=patrol_area_id,
            expected_revision=expected_revision,
            patrol_area_name=patrol_area_name,
            path_json=path_json,
            active_frame_id=map_profile["frame_id"],
            is_enabled=is_enabled,
        )
        if error:
            return error

        try:
            result = self.repository.update_patrol_area(
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return patrol_area_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="순찰 구역 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_patrol_area_update_result(result)

    async def async_update_patrol_area_path(
        self,
        *,
        patrol_area_id,
        expected_revision,
        path_json,
        map_id=None,
    ):
        map_profile, error = await self._async_resolve_map_profile(
            map_id=map_id,
            error_factory=patrol_area_error,
        )
        if error:
            return error

        normalized, error = normalize_patrol_area_path_input(
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
            return patrol_area_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="순찰 경로 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_patrol_area_update_result(result)

    async def async_create_patrol_area(
        self,
        *,
        patrol_area_id,
        patrol_area_name,
        path_json,
        map_id=None,
        is_enabled=True,
    ):
        map_profile, error = await self._async_resolve_active_map(
            map_id=map_id,
            error_factory=patrol_area_error,
        )
        if error:
            return error

        normalized, error = normalize_patrol_area_input(
            patrol_area_id=patrol_area_id,
            patrol_area_name=patrol_area_name,
            path_json=path_json,
            active_frame_id=map_profile["frame_id"],
            is_enabled=is_enabled,
        )
        if error:
            return error

        existing_patrol_area = await self._call_async_or_thread(
            "async_get_patrol_area",
            "get_patrol_area",
            patrol_area_id=normalized["patrol_area_id"],
        )
        if existing_patrol_area:
            return patrol_area_error(
                result_code="CONFLICT",
                reason_code="PATROL_AREA_ID_DUPLICATED",
                result_message="이미 존재하는 순찰 구역 ID입니다.",
            )

        try:
            row = await self._call_async_or_thread(
                "async_create_patrol_area",
                "create_patrol_area",
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return patrol_area_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="순찰 구역 생성 중 DB 쓰기에 실패했습니다.",
            )

        return {
            "result_code": "CREATED",
            "result_message": None,
            "reason_code": None,
            "patrol_area": format_patrol_area(
                row or {},
                include_patrol_path=True,
            ),
        }

    async def async_update_patrol_area(
        self,
        *,
        patrol_area_id,
        expected_revision,
        patrol_area_name,
        path_json,
        is_enabled,
    ):
        map_profile, error = await self._async_resolve_active_map(
            error_factory=patrol_area_error,
        )
        if error:
            return error

        normalized, error = normalize_patrol_area_input(
            patrol_area_id=patrol_area_id,
            expected_revision=expected_revision,
            patrol_area_name=patrol_area_name,
            path_json=path_json,
            active_frame_id=map_profile["frame_id"],
            is_enabled=is_enabled,
        )
        if error:
            return error

        try:
            result = await self._call_async_or_thread(
                "async_update_patrol_area",
                "update_patrol_area",
                map_id=map_profile["map_id"],
                **normalized,
            )
        except Exception:
            return patrol_area_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="순찰 구역 수정 중 DB 쓰기에 실패했습니다.",
            )

        return self._format_patrol_area_update_result(result)

    async def async_get_active_map_bundle(
        self,
        *,
        include_disabled=True,
        include_zone_boundaries=True,
        include_patrol_paths=True,
    ):
        return await self.async_get_map_bundle(
            map_id=None,
            include_disabled=include_disabled,
            include_zone_boundaries=include_zone_boundaries,
            include_patrol_paths=include_patrol_paths,
        )

    async def async_get_map_bundle(
        self,
        *,
        map_id=None,
        include_disabled=True,
        include_zone_boundaries=True,
        include_patrol_paths=True,
    ):
        include_disabled = bool_value(include_disabled)
        include_zone_boundaries = bool_value(include_zone_boundaries)
        include_patrol_paths = bool_value(include_patrol_paths)

        map_profile, error = await self._async_resolve_map_profile(map_id=map_id)
        if error:
            return self._not_found_response(
                result_code=error.get("result_code", "NOT_FOUND"),
                reason_code=error.get("reason_code", "ACTIVE_MAP_NOT_FOUND"),
                result_message=error.get("result_message", "활성 map_profile이 없습니다."),
            )

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
        return self._resolve_map_profile(map_id=map_id, error_factory=error_factory)

    async def _async_resolve_active_map(self, *, map_id=None, error_factory=None):
        return await self._async_resolve_map_profile(
            map_id=map_id,
            error_factory=error_factory,
        )

    def _resolve_map_profile(self, *, map_id=None, error_factory=None):
        error_factory = error_factory or operation_zone_error
        requested_map_id = normalize_optional_text(map_id)
        row = (
            self.repository.get_map_profile(map_id=requested_map_id)
            if requested_map_id
            else self.repository.get_active_map_profile()
        )
        return self._format_map_profile_resolution(
            row,
            requested_map_id=requested_map_id,
            error_factory=error_factory,
        )

    async def _async_resolve_map_profile(self, *, map_id=None, error_factory=None):
        error_factory = error_factory or operation_zone_error
        requested_map_id = normalize_optional_text(map_id)
        if requested_map_id:
            row = await self._call_async_or_thread(
                "async_get_map_profile",
                "get_map_profile",
                map_id=requested_map_id,
            )
        else:
            row = await self._call_async_or_thread(
                "async_get_active_map_profile",
                "get_active_map_profile",
            )
        return self._format_map_profile_resolution(
            row,
            requested_map_id=requested_map_id,
            error_factory=error_factory,
        )

    def _format_map_profile_resolution(
        self,
        row,
        *,
        requested_map_id=None,
        error_factory=None,
    ):
        error_factory = error_factory or operation_zone_error
        if not row:
            reason_code = "MAP_NOT_FOUND" if requested_map_id else "ACTIVE_MAP_NOT_FOUND"
            result_message = (
                "요청한 map_id를 찾을 수 없습니다."
                if requested_map_id
                else "활성 map_profile이 없습니다."
            )
            return None, error_factory(
                result_code="NOT_FOUND",
                reason_code=reason_code,
                result_message=result_message,
            )

        return format_map_profile(row), None

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
            "map_profiles": self._list_map_profiles(),
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

    def _not_found_response(
        self,
        *,
        result_code="NOT_FOUND",
        reason_code="ACTIVE_MAP_NOT_FOUND",
        result_message="활성 map_profile이 없습니다.",
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "generated_at": generated_at(self._clock),
            "map_profile": None,
            "map_profiles": self._list_map_profiles(),
            "operation_zones": [],
            "goal_poses": [],
            "patrol_areas": [],
        }

    def list_map_profiles(self):
        rows = self.repository.list_map_profiles()
        return {
            "result_code": "OK",
            "result_message": None,
            "reason_code": None,
            "generated_at": generated_at(self._clock),
            "map_profiles": [format_map_profile(row) for row in rows or []],
        }

    async def async_list_map_profiles(self):
        rows = await self._call_async_or_thread(
            "async_list_map_profiles",
            "list_map_profiles",
        )
        return {
            "result_code": "OK",
            "result_message": None,
            "reason_code": None,
            "generated_at": generated_at(self._clock),
            "map_profiles": [format_map_profile(row) for row in rows or []],
        }

    def _list_map_profiles(self):
        try:
            rows = self.repository.list_map_profiles()
        except Exception:
            return []
        return [format_map_profile(row) for row in rows or []]

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
            return operation_zone_error(
                result_code="NOT_FOUND",
                reason_code="ZONE_NOT_FOUND",
                result_message="수정할 구역을 찾을 수 없습니다.",
            )
        if status == "REVISION_CONFLICT":
            return operation_zone_error(
                result_code="CONFLICT",
                reason_code="ZONE_REVISION_CONFLICT",
                result_message="구역 revision이 최신 값과 일치하지 않습니다.",
            )
        return operation_zone_error(
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
            return goal_pose_error(
                result_code="NOT_FOUND",
                reason_code="GOAL_POSE_NOT_FOUND",
                result_message="수정할 목적지 좌표를 찾을 수 없습니다.",
            )
        if status == "STALE":
            return goal_pose_error(
                result_code="CONFLICT",
                reason_code="GOAL_POSE_STALE",
                result_message="목적지 좌표가 최신 값과 일치하지 않습니다.",
            )
        return goal_pose_error(
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
            return patrol_area_error(
                result_code="NOT_FOUND",
                reason_code="PATROL_AREA_NOT_FOUND",
                result_message="수정할 순찰 구역을 찾을 수 없습니다.",
            )
        if status == "REVISION_CONFLICT":
            return patrol_area_error(
                result_code="CONFLICT",
                reason_code="PATROL_AREA_REVISION_CONFLICT",
                result_message="순찰 경로 revision이 최신 값과 일치하지 않습니다.",
            )
        return patrol_area_error(
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

    def _validate_goal_pose_zone(self, *, map_id, zone_id):
        if zone_id is None:
            return None

        zone = self.repository.get_operation_zone(map_id=map_id, zone_id=zone_id)
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
            map_id=map_id,
            zone_id=zone_id,
        )
        return self._format_goal_pose_zone_validation(
            map_id=map_id,
            zone=zone,
        )

    @classmethod
    def _format_goal_pose_zone_validation(cls, *, map_id, zone):
        if not zone or zone.get("map_id") != map_id:
            return goal_pose_error(
                result_code="NOT_FOUND",
                reason_code="ZONE_NOT_FOUND",
                result_message="연결할 구역을 찾을 수 없습니다.",
            )
        return None

__all__ = ["CoordinateConfigService"]
