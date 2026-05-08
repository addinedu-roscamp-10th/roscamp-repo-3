import asyncio
from datetime import datetime, timezone

from server.ropi_main_service.application.fms_config_formatters import (
    format_fms_edge,
    format_fms_route,
    format_fms_waypoint,
    format_map_profile,
    generated_at,
)
from server.ropi_main_service.application.fms_config_validators import (
    fms_edge_error,
    fms_route_error,
    fms_waypoint_error,
    normalize_edge_input,
    normalize_route_input,
    normalize_waypoint_input,
)
from server.ropi_main_service.application.formatting import bool_value
from server.ropi_main_service.persistence.repositories.fms_config_repository import (
    FmsConfigRepository,
)


class FmsConfigService:
    def __init__(self, repository=None, clock=None):
        self.repository = repository or FmsConfigRepository()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_active_graph_bundle(
        self,
        *,
        include_disabled=True,
        include_edges=True,
        include_routes=True,
        include_reservations=False,
    ):
        return self.get_graph_bundle(
            map_id=None,
            include_disabled=include_disabled,
            include_edges=include_edges,
            include_routes=include_routes,
            include_reservations=include_reservations,
        )

    def get_graph_bundle(
        self,
        *,
        map_id=None,
        include_disabled=True,
        include_edges=True,
        include_routes=True,
        include_reservations=False,
    ):
        include_disabled = bool_value(include_disabled)

        map_profile, error = self._resolve_map_profile(
            map_id=map_id,
            error_factory=self._not_found_bundle_response,
        )
        if error:
            return self._not_found_bundle_response()

        waypoints = self.repository.get_waypoints(
            map_id=map_profile["map_id"],
            include_disabled=include_disabled,
        )
        edges = (
            self.repository.get_edges(
                map_id=map_profile["map_id"],
                include_disabled=include_disabled,
            )
            if bool_value(include_edges)
            else []
        )
        routes = (
            self.repository.get_routes(
                map_id=map_profile["map_id"],
                include_disabled=include_disabled,
            )
            if bool_value(include_routes)
            else []
        )

        return self._ok_bundle_response(
            map_profile=map_profile,
            waypoints=waypoints,
            edges=edges,
            routes=routes,
            include_edges=include_edges,
            include_routes=include_routes,
            include_reservations=include_reservations,
        )

    async def async_get_active_graph_bundle(
        self,
        *,
        include_disabled=True,
        include_edges=True,
        include_routes=True,
        include_reservations=False,
    ):
        return await self.async_get_graph_bundle(
            map_id=None,
            include_disabled=include_disabled,
            include_edges=include_edges,
            include_routes=include_routes,
            include_reservations=include_reservations,
        )

    async def async_get_graph_bundle(
        self,
        *,
        map_id=None,
        include_disabled=True,
        include_edges=True,
        include_routes=True,
        include_reservations=False,
    ):
        include_disabled = bool_value(include_disabled)

        map_profile, error = await self._async_resolve_map_profile(
            map_id=map_id,
            error_factory=self._not_found_bundle_response,
        )
        if error:
            return self._not_found_bundle_response()

        waypoints = await self._call_async_or_thread(
            "async_get_waypoints",
            "get_waypoints",
            map_id=map_profile["map_id"],
            include_disabled=include_disabled,
        )
        edges = (
            await self._call_async_or_thread(
                "async_get_edges",
                "get_edges",
                map_id=map_profile["map_id"],
                include_disabled=include_disabled,
            )
            if bool_value(include_edges)
            else []
        )
        routes = (
            await self._call_async_or_thread(
                "async_get_routes",
                "get_routes",
                map_id=map_profile["map_id"],
                include_disabled=include_disabled,
            )
            if bool_value(include_routes)
            else []
        )

        return self._ok_bundle_response(
            map_profile=map_profile,
            waypoints=waypoints,
            edges=edges,
            routes=routes,
            include_edges=include_edges,
            include_routes=include_routes,
            include_reservations=include_reservations,
        )

    def upsert_waypoint(
        self,
        *,
        waypoint_id,
        expected_updated_at=None,
        display_name,
        waypoint_type,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        snap_group=None,
        is_enabled,
        map_id=None,
    ):
        active_map, error = self._resolve_active_map(map_id=map_id)
        if error:
            return error

        normalized, error = normalize_waypoint_input(
            waypoint_id=waypoint_id,
            expected_updated_at=expected_updated_at,
            display_name=display_name,
            waypoint_type=waypoint_type,
            pose_x=pose_x,
            pose_y=pose_y,
            pose_yaw=pose_yaw,
            frame_id=frame_id,
            snap_group=snap_group,
            is_enabled=is_enabled,
            active_frame_id=active_map["frame_id"],
        )
        if error:
            return self._with_generated_at(error)

        try:
            result = self.repository.upsert_waypoint(
                map_id=active_map["map_id"],
                **normalized,
            )
        except Exception:
            return self._with_generated_at(
                fms_waypoint_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_WRITE_FAILED",
                    result_message="FMS waypoint 저장 중 DB 쓰기에 실패했습니다.",
                )
            )

        return self._format_waypoint_upsert_result(result)

    def upsert_edge(
        self,
        *,
        edge_id,
        from_waypoint_id,
        to_waypoint_id,
        is_bidirectional,
        is_enabled,
        expected_updated_at=None,
        traversal_cost=None,
        priority=None,
        map_id=None,
    ):
        active_map, error = self._resolve_active_map_for_edge(map_id=map_id)
        if error:
            return error

        normalized, error = normalize_edge_input(
            edge_id=edge_id,
            expected_updated_at=expected_updated_at,
            from_waypoint_id=from_waypoint_id,
            to_waypoint_id=to_waypoint_id,
            is_bidirectional=is_bidirectional,
            traversal_cost=traversal_cost,
            priority=priority,
            is_enabled=is_enabled,
        )
        if error:
            return self._with_generated_at(error)

        _waypoints, error = self._get_endpoint_waypoints(
            map_id=active_map["map_id"],
            from_waypoint_id=normalized["from_waypoint_id"],
            to_waypoint_id=normalized["to_waypoint_id"],
        )
        if error:
            return error

        try:
            result = self.repository.upsert_edge(
                map_id=active_map["map_id"],
                **normalized,
            )
        except Exception:
            return self._with_generated_at(
                fms_edge_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_WRITE_FAILED",
                    result_message="FMS edge 저장 중 DB 쓰기에 실패했습니다.",
                )
            )

        return self._format_edge_upsert_result(result)

    def upsert_route(
        self,
        *,
        route_id,
        route_name,
        route_scope,
        waypoint_sequence,
        is_enabled,
        expected_revision=None,
        map_id=None,
    ):
        active_map, error = self._resolve_active_map_for_route(map_id=map_id)
        if error:
            return error

        normalized, error = normalize_route_input(
            route_id=route_id,
            expected_revision=expected_revision,
            route_name=route_name,
            route_scope=route_scope,
            waypoint_sequence=waypoint_sequence,
            is_enabled=is_enabled,
        )
        if error:
            return self._with_generated_at(error)

        _waypoints, error = self._get_route_waypoints(
            map_id=active_map["map_id"],
            waypoint_sequence=normalized["waypoint_sequence"],
        )
        if error:
            return error

        if normalized["is_enabled"]:
            _edges, error = self._get_route_edges(
                map_id=active_map["map_id"],
                waypoint_sequence=normalized["waypoint_sequence"],
            )
            if error:
                return error

        try:
            result = self.repository.upsert_route(
                map_id=active_map["map_id"],
                **normalized,
            )
        except Exception:
            return self._with_generated_at(
                fms_route_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_WRITE_FAILED",
                    result_message="FMS route 저장 중 DB 쓰기에 실패했습니다.",
                )
            )

        return self._format_route_upsert_result(result)

    async def async_upsert_waypoint(
        self,
        *,
        waypoint_id,
        expected_updated_at=None,
        display_name,
        waypoint_type,
        pose_x,
        pose_y,
        pose_yaw,
        frame_id,
        snap_group=None,
        is_enabled,
        map_id=None,
    ):
        active_map, error = await self._async_resolve_active_map(map_id=map_id)
        if error:
            return error

        normalized, error = normalize_waypoint_input(
            waypoint_id=waypoint_id,
            expected_updated_at=expected_updated_at,
            display_name=display_name,
            waypoint_type=waypoint_type,
            pose_x=pose_x,
            pose_y=pose_y,
            pose_yaw=pose_yaw,
            frame_id=frame_id,
            snap_group=snap_group,
            is_enabled=is_enabled,
            active_frame_id=active_map["frame_id"],
        )
        if error:
            return self._with_generated_at(error)

        try:
            result = await self._call_async_or_thread(
                "async_upsert_waypoint",
                "upsert_waypoint",
                map_id=active_map["map_id"],
                **normalized,
            )
        except Exception:
            return self._with_generated_at(
                fms_waypoint_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_WRITE_FAILED",
                    result_message="FMS waypoint 저장 중 DB 쓰기에 실패했습니다.",
                )
            )

        return self._format_waypoint_upsert_result(result)

    async def async_upsert_edge(
        self,
        *,
        edge_id,
        from_waypoint_id,
        to_waypoint_id,
        is_bidirectional,
        is_enabled,
        expected_updated_at=None,
        traversal_cost=None,
        priority=None,
        map_id=None,
    ):
        active_map, error = await self._async_resolve_active_map_for_edge(map_id=map_id)
        if error:
            return error

        normalized, error = normalize_edge_input(
            edge_id=edge_id,
            expected_updated_at=expected_updated_at,
            from_waypoint_id=from_waypoint_id,
            to_waypoint_id=to_waypoint_id,
            is_bidirectional=is_bidirectional,
            traversal_cost=traversal_cost,
            priority=priority,
            is_enabled=is_enabled,
        )
        if error:
            return self._with_generated_at(error)

        _waypoints, error = await self._async_get_endpoint_waypoints(
            map_id=active_map["map_id"],
            from_waypoint_id=normalized["from_waypoint_id"],
            to_waypoint_id=normalized["to_waypoint_id"],
        )
        if error:
            return error

        try:
            result = await self._call_async_or_thread(
                "async_upsert_edge",
                "upsert_edge",
                map_id=active_map["map_id"],
                **normalized,
            )
        except Exception:
            return self._with_generated_at(
                fms_edge_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_WRITE_FAILED",
                    result_message="FMS edge 저장 중 DB 쓰기에 실패했습니다.",
                )
            )

        return self._format_edge_upsert_result(result)

    async def async_upsert_route(
        self,
        *,
        route_id,
        route_name,
        route_scope,
        waypoint_sequence,
        is_enabled,
        expected_revision=None,
        map_id=None,
    ):
        active_map, error = await self._async_resolve_active_map_for_route(map_id=map_id)
        if error:
            return error

        normalized, error = normalize_route_input(
            route_id=route_id,
            expected_revision=expected_revision,
            route_name=route_name,
            route_scope=route_scope,
            waypoint_sequence=waypoint_sequence,
            is_enabled=is_enabled,
        )
        if error:
            return self._with_generated_at(error)

        _waypoints, error = await self._async_get_route_waypoints(
            map_id=active_map["map_id"],
            waypoint_sequence=normalized["waypoint_sequence"],
        )
        if error:
            return error

        if normalized["is_enabled"]:
            _edges, error = await self._async_get_route_edges(
                map_id=active_map["map_id"],
                waypoint_sequence=normalized["waypoint_sequence"],
            )
            if error:
                return error

        try:
            result = await self._call_async_or_thread(
                "async_upsert_route",
                "upsert_route",
                map_id=active_map["map_id"],
                **normalized,
            )
        except Exception:
            return self._with_generated_at(
                fms_route_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_WRITE_FAILED",
                    result_message="FMS route 저장 중 DB 쓰기에 실패했습니다.",
                )
            )

        return self._format_route_upsert_result(result)

    def _resolve_active_map(self, *, map_id=None):
        return self._resolve_map_profile(
            map_id=map_id,
            error_factory=self._not_found_waypoint_response,
        )

    def _resolve_active_map_for_edge(self, *, map_id=None):
        return self._resolve_map_profile(
            map_id=map_id,
            error_factory=self._not_found_edge_response,
        )

    def _resolve_active_map_for_route(self, *, map_id=None):
        return self._resolve_map_profile(
            map_id=map_id,
            error_factory=self._not_found_route_response,
        )

    async def _async_resolve_active_map(self, *, map_id=None):
        return await self._async_resolve_map_profile(
            map_id=map_id,
            error_factory=self._not_found_waypoint_response,
        )

    async def _async_resolve_active_map_for_edge(self, *, map_id=None):
        return await self._async_resolve_map_profile(
            map_id=map_id,
            error_factory=self._not_found_edge_response,
        )

    async def _async_resolve_active_map_for_route(self, *, map_id=None):
        return await self._async_resolve_map_profile(
            map_id=map_id,
            error_factory=self._not_found_route_response,
        )

    def _resolve_map_profile(self, *, map_id=None, error_factory):
        requested_map_id = str(map_id or "").strip()
        row = (
            self.repository.get_map_profile(map_id=requested_map_id)
            if requested_map_id
            else self.repository.get_active_map_profile()
        )
        if not row:
            return None, error_factory()
        return format_map_profile(row), None

    async def _async_resolve_map_profile(self, *, map_id=None, error_factory):
        requested_map_id = str(map_id or "").strip()
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
        if not row:
            return None, error_factory()
        return format_map_profile(row), None

    async def _call_async_or_thread(self, async_name, sync_name, **kwargs):
        async_method = getattr(self.repository, async_name, None)
        if async_method is not None:
            return await async_method(**kwargs)

        sync_method = getattr(self.repository, sync_name)
        return await asyncio.to_thread(sync_method, **kwargs)

    def _get_endpoint_waypoints(self, *, map_id, from_waypoint_id, to_waypoint_id):
        try:
            waypoints = self.repository.get_waypoints(
                map_id=map_id,
                include_disabled=True,
            )
        except Exception:
            return None, self._with_generated_at(
                fms_edge_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_READ_FAILED",
                    result_message="FMS waypoint 조회에 실패했습니다.",
                )
            )
        error = self._endpoint_waypoint_error(
            waypoints,
            from_waypoint_id=from_waypoint_id,
            to_waypoint_id=to_waypoint_id,
        )
        return waypoints, error

    async def _async_get_endpoint_waypoints(
        self,
        *,
        map_id,
        from_waypoint_id,
        to_waypoint_id,
    ):
        try:
            waypoints = await self._call_async_or_thread(
                "async_get_waypoints",
                "get_waypoints",
                map_id=map_id,
                include_disabled=True,
            )
        except Exception:
            return None, self._with_generated_at(
                fms_edge_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_READ_FAILED",
                    result_message="FMS waypoint 조회에 실패했습니다.",
                )
            )
        error = self._endpoint_waypoint_error(
            waypoints,
            from_waypoint_id=from_waypoint_id,
            to_waypoint_id=to_waypoint_id,
        )
        return waypoints, error

    def _endpoint_waypoint_error(
        self,
        waypoints,
        *,
        from_waypoint_id,
        to_waypoint_id,
    ):
        waypoint_ids = {str(row.get("waypoint_id")) for row in waypoints or []}
        if from_waypoint_id in waypoint_ids and to_waypoint_id in waypoint_ids:
            return None
        return self._with_generated_at(
            fms_edge_error(
                result_code="INVALID_REQUEST",
                reason_code="EDGE_WAYPOINT_NOT_FOUND",
                result_message="FMS edge endpoint waypoint를 찾을 수 없습니다.",
            )
        )

    def _get_route_waypoints(self, *, map_id, waypoint_sequence):
        try:
            waypoints = self.repository.get_waypoints(
                map_id=map_id,
                include_disabled=True,
            )
        except Exception:
            return None, self._with_generated_at(
                fms_route_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_READ_FAILED",
                    result_message="FMS waypoint 조회에 실패했습니다.",
                )
            )
        return waypoints, self._route_waypoint_error(waypoints, waypoint_sequence)

    async def _async_get_route_waypoints(self, *, map_id, waypoint_sequence):
        try:
            waypoints = await self._call_async_or_thread(
                "async_get_waypoints",
                "get_waypoints",
                map_id=map_id,
                include_disabled=True,
            )
        except Exception:
            return None, self._with_generated_at(
                fms_route_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_READ_FAILED",
                    result_message="FMS waypoint 조회에 실패했습니다.",
                )
            )
        return waypoints, self._route_waypoint_error(waypoints, waypoint_sequence)

    def _get_route_edges(self, *, map_id, waypoint_sequence):
        try:
            edges = self.repository.get_edges(
                map_id=map_id,
                include_disabled=True,
            )
        except Exception:
            return None, self._with_generated_at(
                fms_route_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_READ_FAILED",
                    result_message="FMS edge 조회에 실패했습니다.",
                )
            )
        return edges, self._route_edge_error(edges, waypoint_sequence)

    async def _async_get_route_edges(self, *, map_id, waypoint_sequence):
        try:
            edges = await self._call_async_or_thread(
                "async_get_edges",
                "get_edges",
                map_id=map_id,
                include_disabled=True,
            )
        except Exception:
            return None, self._with_generated_at(
                fms_route_error(
                    result_code="UNAVAILABLE",
                    reason_code="CONFIG_READ_FAILED",
                    result_message="FMS edge 조회에 실패했습니다.",
                )
            )
        return edges, self._route_edge_error(edges, waypoint_sequence)

    def _route_waypoint_error(self, waypoints, waypoint_sequence):
        waypoint_ids = {str(row.get("waypoint_id")) for row in waypoints or []}
        route_waypoint_ids = [
            str(row.get("waypoint_id")) for row in waypoint_sequence or []
        ]
        if all(waypoint_id in waypoint_ids for waypoint_id in route_waypoint_ids):
            return None
        return self._with_generated_at(
            fms_route_error(
                result_code="INVALID_REQUEST",
                reason_code="ROUTE_WAYPOINT_NOT_FOUND",
                result_message="FMS route waypoint를 찾을 수 없습니다.",
            )
        )

    def _route_edge_error(self, edges, waypoint_sequence):
        for index in range(len(waypoint_sequence or []) - 1):
            from_waypoint_id = waypoint_sequence[index].get("waypoint_id")
            to_waypoint_id = waypoint_sequence[index + 1].get("waypoint_id")
            if not self._has_enabled_edge(
                edges,
                from_waypoint_id=from_waypoint_id,
                to_waypoint_id=to_waypoint_id,
            ):
                return self._with_generated_at(
                    fms_route_error(
                        result_code="INVALID_REQUEST",
                        reason_code="ROUTE_EDGE_NOT_CONNECTED",
                        result_message="FMS route waypoint 사이의 enabled edge가 없습니다.",
                    )
                )
        return None

    @staticmethod
    def _has_enabled_edge(edges, *, from_waypoint_id, to_waypoint_id):
        for edge in edges or []:
            if not bool_value(edge.get("is_enabled")):
                continue
            edge_from = edge.get("from_waypoint_id")
            edge_to = edge.get("to_waypoint_id")
            if edge_from == from_waypoint_id and edge_to == to_waypoint_id:
                return True
            if (
                bool_value(edge.get("is_bidirectional"))
                and edge_from == to_waypoint_id
                and edge_to == from_waypoint_id
            ):
                return True
        return False

    def _ok_bundle_response(
        self,
        *,
        map_profile,
        waypoints,
        edges,
        routes,
        include_edges,
        include_routes,
        include_reservations,
    ):
        return {
            "result_code": "OK",
            "result_message": None,
            "reason_code": None,
            "generated_at": generated_at(self._clock),
            "map_profile": map_profile,
            "waypoints": [format_fms_waypoint(row) for row in waypoints or []],
            "edges": [format_fms_edge(row) for row in edges or []]
            if bool_value(include_edges)
            else [],
            "routes": [format_fms_route(row) for row in routes or []]
            if bool_value(include_routes)
            else [],
            "reservations": [] if bool_value(include_reservations) else [],
        }

    def _not_found_bundle_response(self):
        return {
            "result_code": "NOT_FOUND",
            "result_message": "active map이 설정되어 있지 않습니다.",
            "reason_code": "ACTIVE_MAP_NOT_FOUND",
            "generated_at": generated_at(self._clock),
            "map_profile": None,
            "waypoints": [],
            "edges": [],
            "routes": [],
            "reservations": [],
        }

    def _not_found_waypoint_response(self):
        return {
            "result_code": "NOT_FOUND",
            "result_message": "active map이 설정되어 있지 않습니다.",
            "reason_code": "ACTIVE_MAP_NOT_FOUND",
            "generated_at": generated_at(self._clock),
            "waypoint": None,
        }

    def _not_found_edge_response(self):
        return {
            "result_code": "NOT_FOUND",
            "result_message": "active map이 설정되어 있지 않습니다.",
            "reason_code": "ACTIVE_MAP_NOT_FOUND",
            "generated_at": generated_at(self._clock),
            "edge": None,
        }

    def _not_found_route_response(self):
        return {
            "result_code": "NOT_FOUND",
            "result_message": "active map이 설정되어 있지 않습니다.",
            "reason_code": "ACTIVE_MAP_NOT_FOUND",
            "generated_at": generated_at(self._clock),
            "route": None,
        }

    def _format_waypoint_upsert_result(self, result):
        status = (result or {}).get("status")
        waypoint = (result or {}).get("waypoint")

        if status == "UPSERTED":
            return {
                "result_code": "OK",
                "result_message": None,
                "reason_code": None,
                "generated_at": generated_at(self._clock),
                "waypoint": format_fms_waypoint(waypoint),
            }
        if status == "STALE":
            return {
                "result_code": "CONFLICT",
                "result_message": "FMS waypoint가 다른 작업에 의해 먼저 변경되었습니다.",
                "reason_code": "WAYPOINT_STALE",
                "generated_at": generated_at(self._clock),
                "waypoint": format_fms_waypoint(waypoint) if waypoint else None,
            }
        if status == "NOT_FOUND":
            return {
                "result_code": "NOT_FOUND",
                "result_message": "FMS waypoint를 찾을 수 없습니다.",
                "reason_code": "WAYPOINT_NOT_FOUND",
                "generated_at": generated_at(self._clock),
                "waypoint": None,
            }
        if status == "MAP_MISMATCH":
            return {
                "result_code": "CONFLICT",
                "result_message": "waypoint_id가 다른 map에 이미 연결되어 있습니다.",
                "reason_code": "WAYPOINT_MAP_MISMATCH",
                "generated_at": generated_at(self._clock),
                "waypoint": format_fms_waypoint(waypoint) if waypoint else None,
            }

        return self._with_generated_at(
            fms_waypoint_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="FMS waypoint 저장 결과를 해석할 수 없습니다.",
            )
        )

    def _format_edge_upsert_result(self, result):
        status = (result or {}).get("status")
        edge = (result or {}).get("edge")

        if status == "UPSERTED":
            return {
                "result_code": "OK",
                "result_message": None,
                "reason_code": None,
                "generated_at": generated_at(self._clock),
                "edge": format_fms_edge(edge),
            }
        if status == "STALE":
            return {
                "result_code": "CONFLICT",
                "result_message": "FMS edge가 다른 작업에 의해 먼저 변경되었습니다.",
                "reason_code": "EDGE_STALE",
                "generated_at": generated_at(self._clock),
                "edge": format_fms_edge(edge) if edge else None,
            }
        if status == "NOT_FOUND":
            return {
                "result_code": "NOT_FOUND",
                "result_message": "FMS edge를 찾을 수 없습니다.",
                "reason_code": "EDGE_NOT_FOUND",
                "generated_at": generated_at(self._clock),
                "edge": None,
            }
        if status == "MAP_MISMATCH":
            return {
                "result_code": "CONFLICT",
                "result_message": "edge_id가 다른 map에 이미 연결되어 있습니다.",
                "reason_code": "EDGE_MAP_MISMATCH",
                "generated_at": generated_at(self._clock),
                "edge": format_fms_edge(edge) if edge else None,
            }

        return self._with_generated_at(
            fms_edge_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="FMS edge 저장 결과를 해석할 수 없습니다.",
            )
        )

    def _format_route_upsert_result(self, result):
        status = (result or {}).get("status")
        route = (result or {}).get("route")

        if status == "UPSERTED":
            return {
                "result_code": "OK",
                "result_message": None,
                "reason_code": None,
                "generated_at": generated_at(self._clock),
                "route": format_fms_route(route),
            }
        if status == "STALE":
            return {
                "result_code": "CONFLICT",
                "result_message": "FMS route가 다른 작업에 의해 먼저 변경되었습니다.",
                "reason_code": "ROUTE_STALE",
                "generated_at": generated_at(self._clock),
                "route": format_fms_route(route) if route else None,
            }
        if status == "NOT_FOUND":
            return {
                "result_code": "NOT_FOUND",
                "result_message": "FMS route를 찾을 수 없습니다.",
                "reason_code": "ROUTE_NOT_FOUND",
                "generated_at": generated_at(self._clock),
                "route": None,
            }
        if status == "MAP_MISMATCH":
            return {
                "result_code": "CONFLICT",
                "result_message": "route_id가 다른 map에 이미 연결되어 있습니다.",
                "reason_code": "ROUTE_MAP_MISMATCH",
                "generated_at": generated_at(self._clock),
                "route": format_fms_route(route) if route else None,
            }

        return self._with_generated_at(
            fms_route_error(
                result_code="UNAVAILABLE",
                reason_code="CONFIG_WRITE_FAILED",
                result_message="FMS route 저장 결과를 해석할 수 없습니다.",
            )
        )

    def _with_generated_at(self, response):
        return {
            **response,
            "generated_at": generated_at(self._clock),
        }


__all__ = ["FmsConfigService"]
