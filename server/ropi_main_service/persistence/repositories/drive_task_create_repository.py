import math

from server.ropi_main_service.application.drive_config import get_drive_runtime_config
from server.ropi_main_service.persistence.async_connection import async_transaction
from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.repositories.drive_task_repository import (
    DriveTaskRepository,
)
from server.ropi_main_service.persistence.repositories.idempotency_repository import (
    IdempotencyRepository,
)
from server.ropi_main_service.persistence.repositories.task_request_common import (
    parse_numeric_identifier,
)
from server.ropi_main_service.persistence.sql_loader import load_sql


DRIVE_CREATE_SCOPE = "DRIVE_CREATE_TASK"


class DriveRouteSnapshotBuilder:
    @staticmethod
    def build(route):
        sequence = route.get("waypoint_sequence")
        if not isinstance(sequence, list) or len(sequence) < 2:
            raise ValueError("주행 경로 waypoint가 2개 이상 필요합니다.")

        ordered = sorted(sequence, key=lambda row: int(row.get("sequence_no") or 0))
        frame_id = str(ordered[0].get("frame_id") or "map").strip() or "map"
        poses = []
        for row in ordered:
            row_frame_id = str(row.get("frame_id") or frame_id).strip() or frame_id
            if row_frame_id != frame_id:
                raise ValueError("주행 경로 waypoint frame_id가 일치하지 않습니다.")

            poses.append(
                {
                    "sequence_no": int(row.get("sequence_no") or len(poses) + 1),
                    "waypoint_id": str(row.get("waypoint_id") or "").strip(),
                    "x": DriveRouteSnapshotBuilder._float(row.get("pose_x")),
                    "y": DriveRouteSnapshotBuilder._float(row.get("pose_y")),
                    "yaw": DriveRouteSnapshotBuilder._resolve_yaw(row),
                    "stop_required": bool(row.get("stop_required", True)),
                    "dwell_sec": DriveRouteSnapshotBuilder._optional_float(
                        row.get("dwell_sec")
                    ),
                }
            )

        return {
            "path_json": {"header": {"frame_id": frame_id}, "poses": poses},
            "frame_id": frame_id,
            "waypoint_count": len(poses),
        }

    @staticmethod
    def _resolve_yaw(row):
        yaw_policy = str(row.get("yaw_policy") or "").strip().upper()
        if yaw_policy == "FIXED" and row.get("fixed_pose_yaw") is not None:
            return DriveRouteSnapshotBuilder._float(row.get("fixed_pose_yaw"))
        return DriveRouteSnapshotBuilder._float(row.get("pose_yaw"))

    @staticmethod
    def _float(value):
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("주행 경로 pose 값이 올바르지 않습니다.") from exc
        if not math.isfinite(result):
            raise ValueError("주행 경로 pose 값이 올바르지 않습니다.")
        return result

    @staticmethod
    def _optional_float(value):
        if value in (None, ""):
            return None
        return DriveRouteSnapshotBuilder._float(value)


class DriveTaskCreateRepository:
    def __init__(
        self,
        *,
        runtime_config=None,
        drive_task_repository=None,
        idempotency_repository=None,
        connection_factory=None,
        async_transaction_factory=None,
        caregiver_exists=None,
        async_caregiver_exists=None,
        fetch_route_by_id=None,
        async_fetch_route_by_id=None,
    ):
        self.runtime_config = runtime_config or get_drive_runtime_config()
        self.drive_task_repository = drive_task_repository or DriveTaskRepository()
        self.idempotency_repository = idempotency_repository or IdempotencyRepository()
        self.connection_factory = connection_factory or get_connection
        self.async_transaction_factory = async_transaction_factory or async_transaction
        self.caregiver_exists = caregiver_exists or self._caregiver_exists
        self.async_caregiver_exists = (
            async_caregiver_exists or self._async_caregiver_exists
        )
        self.fetch_route_by_id = fetch_route_by_id or self._fetch_route_by_id
        self.async_fetch_route_by_id = (
            async_fetch_route_by_id or self._async_fetch_route_by_id
        )

    def create_drive_task(
        self,
        request_id,
        caregiver_id,
        robot_id,
        route_id,
        priority,
        notes,
        idempotency_key,
    ):
        numeric_caregiver_id = parse_numeric_identifier(caregiver_id)
        normalized_robot_id = str(robot_id or "").strip()
        normalized_route_id = str(route_id or "").strip()
        request_hash = self.idempotency_repository.build_request_hash(
            request_id=request_id,
            caregiver_id=numeric_caregiver_id,
            robot_id=normalized_robot_id,
            route_id=normalized_route_id,
            priority=priority,
            notes=notes,
        )

        if numeric_caregiver_id is None:
            return self.build_drive_task_response(
                result_code="REJECTED",
                result_message="caregiver_id를 확인할 수 없습니다.",
                reason_code="REQUESTER_NOT_AUTHORIZED",
            )
        if not self.runtime_config.is_robot_allowed(normalized_robot_id):
            return self.build_drive_task_response(
                result_code="REJECTED",
                result_message="허용되지 않은 FMS 주행 로봇입니다.",
                reason_code="DRIVE_ROBOT_NOT_ALLOWED",
            )

        conn = self.connection_factory()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                existing_response = self.idempotency_repository.find_response(
                    cur,
                    requester_id=str(numeric_caregiver_id),
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    scope=DRIVE_CREATE_SCOPE,
                )
                if existing_response is not None:
                    conn.commit()
                    return existing_response

                if not self.caregiver_exists(cur, numeric_caregiver_id):
                    conn.rollback()
                    return self.build_drive_task_response(
                        result_code="REJECTED",
                        result_message="요청자를 확인할 수 없습니다.",
                        reason_code="REQUESTER_NOT_AUTHORIZED",
                    )

                route = self.fetch_route_by_id(cur, normalized_route_id)
                route_response = self.validate_route_for_create(route)
                if route_response is not None:
                    conn.rollback()
                    return route_response

                response = self._create_accepted_drive_task(
                    cur,
                    request_id=request_id,
                    caregiver_id=numeric_caregiver_id,
                    robot_id=normalized_robot_id,
                    route_id=normalized_route_id,
                    priority=priority,
                    notes=notes,
                    idempotency_key=idempotency_key,
                    route=route,
                )
                self.idempotency_repository.insert_record(
                    cur,
                    requester_id=str(numeric_caregiver_id),
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=response,
                    task_id=response["task_id"],
                    scope=DRIVE_CREATE_SCOPE,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_create_drive_task(
        self,
        request_id,
        caregiver_id,
        robot_id,
        route_id,
        priority,
        notes,
        idempotency_key,
    ):
        numeric_caregiver_id = parse_numeric_identifier(caregiver_id)
        normalized_robot_id = str(robot_id or "").strip()
        normalized_route_id = str(route_id or "").strip()
        request_hash = self.idempotency_repository.build_request_hash(
            request_id=request_id,
            caregiver_id=numeric_caregiver_id,
            robot_id=normalized_robot_id,
            route_id=normalized_route_id,
            priority=priority,
            notes=notes,
        )

        if numeric_caregiver_id is None:
            return self.build_drive_task_response(
                result_code="REJECTED",
                result_message="caregiver_id를 확인할 수 없습니다.",
                reason_code="REQUESTER_NOT_AUTHORIZED",
            )
        if not self.runtime_config.is_robot_allowed(normalized_robot_id):
            return self.build_drive_task_response(
                result_code="REJECTED",
                result_message="허용되지 않은 FMS 주행 로봇입니다.",
                reason_code="DRIVE_ROBOT_NOT_ALLOWED",
            )

        async with self.async_transaction_factory() as cur:
            existing_response = await self.idempotency_repository.async_find_response(
                cur,
                requester_id=str(numeric_caregiver_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                scope=DRIVE_CREATE_SCOPE,
            )
            if existing_response is not None:
                return existing_response

            if not await self.async_caregiver_exists(cur, numeric_caregiver_id):
                return self.build_drive_task_response(
                    result_code="REJECTED",
                    result_message="요청자를 확인할 수 없습니다.",
                    reason_code="REQUESTER_NOT_AUTHORIZED",
                )

            route = await self.async_fetch_route_by_id(cur, normalized_route_id)
            route_response = self.validate_route_for_create(route)
            if route_response is not None:
                return route_response

            response = await self._async_create_accepted_drive_task(
                cur,
                request_id=request_id,
                caregiver_id=numeric_caregiver_id,
                robot_id=normalized_robot_id,
                route_id=normalized_route_id,
                priority=priority,
                notes=notes,
                idempotency_key=idempotency_key,
                route=route,
            )
            await self.idempotency_repository.async_insert_record(
                cur,
                requester_id=str(numeric_caregiver_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response=response,
                task_id=response["task_id"],
                scope=DRIVE_CREATE_SCOPE,
            )
            return response

    def _create_accepted_drive_task(
        self,
        cur,
        *,
        request_id,
        caregiver_id,
        robot_id,
        route_id,
        priority,
        notes,
        idempotency_key,
        route,
    ):
        snapshot = DriveRouteSnapshotBuilder.build(route)
        task_id = self.drive_task_repository.create_drive_task_records(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            caregiver_id=caregiver_id,
            priority=priority,
            assigned_robot_id=robot_id,
            route_id=route_id,
            route_revision=int(route["revision"]),
            route_name=route["route_name"],
            map_id=route["map_id"],
            frame_id=snapshot["frame_id"],
            waypoint_count=snapshot["waypoint_count"],
            path_snapshot_json=snapshot["path_json"],
            notes=notes,
        )
        return self._build_accepted_drive_task_response(
            task_id=task_id,
            robot_id=robot_id,
            route=route,
            snapshot=snapshot,
        )

    async def _async_create_accepted_drive_task(self, cur, **kwargs):
        route = kwargs["route"]
        snapshot = DriveRouteSnapshotBuilder.build(route)
        task_id = await self.drive_task_repository.async_create_drive_task_records(
            cur,
            request_id=kwargs["request_id"],
            idempotency_key=kwargs["idempotency_key"],
            caregiver_id=kwargs["caregiver_id"],
            priority=kwargs["priority"],
            assigned_robot_id=kwargs["robot_id"],
            route_id=kwargs["route_id"],
            route_revision=int(route["revision"]),
            route_name=route["route_name"],
            map_id=route["map_id"],
            frame_id=snapshot["frame_id"],
            waypoint_count=snapshot["waypoint_count"],
            path_snapshot_json=snapshot["path_json"],
            notes=kwargs.get("notes"),
        )
        return self._build_accepted_drive_task_response(
            task_id=task_id,
            robot_id=kwargs["robot_id"],
            route=route,
            snapshot=snapshot,
        )

    def _build_accepted_drive_task_response(
        self,
        *,
        task_id,
        robot_id,
        route,
        snapshot,
    ):
        return self.build_drive_task_response(
            result_code="ACCEPTED",
            task_id=task_id,
            task_status="WAITING_DISPATCH",
            phase="REQUESTED",
            assigned_robot_id=robot_id,
            map_id=route["map_id"],
            route_id=route["route_id"],
            route_name=route["route_name"],
            route_revision=int(route["revision"]),
            waypoint_count=snapshot["waypoint_count"],
        )

    def validate_route_for_create(self, route):
        if not route:
            return self.build_drive_task_response(
                result_code="REJECTED",
                result_message="요청한 route_id를 찾을 수 없습니다.",
                reason_code="DRIVE_ROUTE_NOT_FOUND",
            )

        if str(route.get("map_id") or "").strip() != self.runtime_config.map_id:
            return self.build_drive_task_response(
                result_code="REJECTED",
                result_message="현재 FMS 맵과 다른 route입니다.",
                reason_code="DRIVE_ROUTE_MAP_MISMATCH",
                route_id=route.get("route_id"),
                route_name=route.get("route_name"),
                route_revision=route.get("revision"),
                map_id=route.get("map_id"),
            )

        if not bool(route.get("is_enabled")):
            return self.build_drive_task_response(
                result_code="REJECTED",
                result_message="비활성화된 FMS route입니다.",
                reason_code="DRIVE_ROUTE_DISABLED",
                route_id=route.get("route_id"),
                route_name=route.get("route_name"),
                route_revision=route.get("revision"),
                map_id=route.get("map_id"),
            )

        try:
            DriveRouteSnapshotBuilder.build(route)
        except ValueError as exc:
            return self.build_drive_task_response(
                result_code="REJECTED",
                result_message=str(exc),
                reason_code="DRIVE_ROUTE_CONFIG_MISSING",
                route_id=route.get("route_id"),
                route_name=route.get("route_name"),
                route_revision=route.get("revision"),
                map_id=route.get("map_id"),
            )

        return None

    @staticmethod
    def _caregiver_exists(cur, caregiver_id) -> bool:
        cur.execute(load_sql("task_request/caregiver_exists.sql"), (caregiver_id,))
        return cur.fetchone() is not None

    @staticmethod
    async def _async_caregiver_exists(cur, caregiver_id) -> bool:
        await cur.execute(load_sql("task_request/caregiver_exists.sql"), (caregiver_id,))
        return await cur.fetchone() is not None

    def _fetch_route_by_id(self, cur, route_id):
        cur.execute(
            load_sql("drive/find_drive_route_by_id.sql"),
            (route_id, self.runtime_config.map_id),
        )
        return self._route_from_rows(cur.fetchall())

    async def _async_fetch_route_by_id(self, cur, route_id):
        await cur.execute(
            load_sql("drive/find_drive_route_by_id.sql"),
            (route_id, self.runtime_config.map_id),
        )
        return self._route_from_rows(await cur.fetchall())

    @staticmethod
    def _route_from_rows(rows):
        rows = list(rows or [])
        if not rows:
            return None

        first = rows[0]
        return {
            "route_id": first["route_id"],
            "map_id": first["map_id"],
            "route_name": first["route_name"],
            "route_scope": first["route_scope"],
            "revision": first["revision"],
            "is_enabled": first["is_enabled"],
            "waypoint_sequence": [
                {
                    "sequence_no": row["sequence_no"],
                    "waypoint_id": row["waypoint_id"],
                    "yaw_policy": row["yaw_policy"],
                    "fixed_pose_yaw": row["fixed_pose_yaw"],
                    "stop_required": row["stop_required"],
                    "dwell_sec": row["dwell_sec"],
                    "pose_x": row["pose_x"],
                    "pose_y": row["pose_y"],
                    "pose_yaw": row["pose_yaw"],
                    "frame_id": row["frame_id"],
                }
                for row in rows
            ],
        }

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()

    @staticmethod
    def build_drive_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_type="DRIVE",
        task_status=None,
        phase=None,
        assigned_robot_id=None,
        map_id=None,
        route_id=None,
        route_name=None,
        route_revision=None,
        waypoint_count=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_type": task_type,
            "task_status": task_status,
            "phase": phase,
            "assigned_robot_id": assigned_robot_id,
            "map_id": map_id,
            "route_id": route_id,
            "route_name": route_name,
            "route_revision": route_revision,
            "waypoint_count": waypoint_count,
        }


__all__ = [
    "DRIVE_CREATE_SCOPE",
    "DriveRouteSnapshotBuilder",
    "DriveTaskCreateRepository",
]
