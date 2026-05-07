import json

from server.ropi_main_service.application.patrol_config import get_patrol_runtime_config
from server.ropi_main_service.persistence.async_connection import async_transaction
from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.repositories.idempotency_repository import (
    IdempotencyRepository,
)
from server.ropi_main_service.persistence.repositories.patrol_task_repository import (
    PatrolTaskRepository,
)
from server.ropi_main_service.persistence.sql_loader import load_sql


PATROL_CREATE_SCOPE = "PATROL_CREATE_TASK"


class PatrolPathSnapshotBuilder:
    @staticmethod
    def build(area):
        raw_path = area.get("path_json")
        if isinstance(raw_path, str):
            try:
                path_json = json.loads(raw_path)
            except json.JSONDecodeError as exc:
                raise ValueError("순찰 경로 JSON을 해석할 수 없습니다.") from exc
        elif isinstance(raw_path, dict):
            path_json = raw_path
        else:
            raise ValueError("순찰 경로 설정이 없습니다.")

        poses = path_json.get("poses")
        if not isinstance(poses, list) or not poses:
            raise ValueError("순찰 경로 waypoint가 비어 있습니다.")

        header = path_json.get("header") if isinstance(path_json.get("header"), dict) else {}
        frame_id = str(header.get("frame_id") or area.get("frame_id") or "map").strip()
        return {
            "path_json": path_json,
            "frame_id": frame_id or "map",
            "waypoint_count": len(poses),
        }


class PatrolTaskCreateRepository:
    def __init__(
        self,
        *,
        runtime_config=None,
        patrol_task_repository=None,
        idempotency_repository=None,
        connection_factory=None,
        async_transaction_factory=None,
        caregiver_exists=None,
        async_caregiver_exists=None,
        fetch_patrol_area_by_id=None,
        async_fetch_patrol_area_by_id=None,
    ):
        self.runtime_config = runtime_config or get_patrol_runtime_config()
        self.patrol_task_repository = patrol_task_repository or PatrolTaskRepository()
        self.idempotency_repository = idempotency_repository or IdempotencyRepository()
        self.connection_factory = connection_factory or get_connection
        self.async_transaction_factory = async_transaction_factory or async_transaction
        self.caregiver_exists = caregiver_exists or self._caregiver_exists
        self.async_caregiver_exists = (
            async_caregiver_exists or self._async_caregiver_exists
        )
        self.fetch_patrol_area_by_id = (
            fetch_patrol_area_by_id or self._fetch_patrol_area_by_id
        )
        self.async_fetch_patrol_area_by_id = (
            async_fetch_patrol_area_by_id or self._async_fetch_patrol_area_by_id
        )

    def create_patrol_task(
        self,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
    ):
        numeric_caregiver_id = self._parse_numeric_identifier(caregiver_id)
        normalized_area_id = str(patrol_area_id or "").strip()
        request_hash = self.idempotency_repository.build_request_hash(
            request_id=request_id,
            caregiver_id=numeric_caregiver_id,
            patrol_area_id=normalized_area_id,
            priority=priority,
        )

        if numeric_caregiver_id is None:
            return self.build_patrol_task_response(
                result_code="REJECTED",
                result_message="caregiver_id를 확인할 수 없습니다.",
                reason_code="REQUESTER_NOT_AUTHORIZED",
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
                    scope=PATROL_CREATE_SCOPE,
                )
                if existing_response is not None:
                    conn.commit()
                    return existing_response

                if not self.caregiver_exists(cur, numeric_caregiver_id):
                    conn.rollback()
                    return self.build_patrol_task_response(
                        result_code="REJECTED",
                        result_message="요청자를 확인할 수 없습니다.",
                        reason_code="REQUESTER_NOT_AUTHORIZED",
                    )

                area = self.fetch_patrol_area_by_id(cur, normalized_area_id)
                area_response = self.validate_patrol_area_for_create(area)
                if area_response is not None:
                    conn.rollback()
                    return area_response

                response = self._create_accepted_patrol_task(
                    cur,
                    request_id=request_id,
                    caregiver_id=numeric_caregiver_id,
                    patrol_area_id=normalized_area_id,
                    priority=priority,
                    idempotency_key=idempotency_key,
                    area=area,
                )
                self.idempotency_repository.insert_record(
                    cur,
                    requester_id=str(numeric_caregiver_id),
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=response,
                    task_id=response["task_id"],
                    scope=PATROL_CREATE_SCOPE,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_create_patrol_task(
        self,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
    ):
        numeric_caregiver_id = self._parse_numeric_identifier(caregiver_id)
        normalized_area_id = str(patrol_area_id or "").strip()
        request_hash = self.idempotency_repository.build_request_hash(
            request_id=request_id,
            caregiver_id=numeric_caregiver_id,
            patrol_area_id=normalized_area_id,
            priority=priority,
        )

        if numeric_caregiver_id is None:
            return self.build_patrol_task_response(
                result_code="REJECTED",
                result_message="caregiver_id를 확인할 수 없습니다.",
                reason_code="REQUESTER_NOT_AUTHORIZED",
            )

        async with self.async_transaction_factory() as cur:
            existing_response = await self.idempotency_repository.async_find_response(
                cur,
                requester_id=str(numeric_caregiver_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                scope=PATROL_CREATE_SCOPE,
            )
            if existing_response is not None:
                return existing_response

            if not await self.async_caregiver_exists(cur, numeric_caregiver_id):
                return self.build_patrol_task_response(
                    result_code="REJECTED",
                    result_message="요청자를 확인할 수 없습니다.",
                    reason_code="REQUESTER_NOT_AUTHORIZED",
                )

            area = await self.async_fetch_patrol_area_by_id(cur, normalized_area_id)
            area_response = self.validate_patrol_area_for_create(area)
            if area_response is not None:
                return area_response

            response = await self._async_create_accepted_patrol_task(
                cur,
                request_id=request_id,
                caregiver_id=numeric_caregiver_id,
                patrol_area_id=normalized_area_id,
                priority=priority,
                idempotency_key=idempotency_key,
                area=area,
            )
            await self.idempotency_repository.async_insert_record(
                cur,
                requester_id=str(numeric_caregiver_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response=response,
                task_id=response["task_id"],
                scope=PATROL_CREATE_SCOPE,
            )
            return response

    def _create_accepted_patrol_task(
        self,
        cur,
        *,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
        area,
    ):
        snapshot = PatrolPathSnapshotBuilder.build(area)
        task_id = self.patrol_task_repository.create_patrol_task_records(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            caregiver_id=caregiver_id,
            priority=priority,
            assigned_robot_id=self.runtime_config.pinky_id,
            patrol_area_id=patrol_area_id,
            patrol_area_revision=int(area["revision"]),
            patrol_area_name=area["patrol_area_name"],
            map_id=area["map_id"],
            frame_id=snapshot["frame_id"],
            waypoint_count=snapshot["waypoint_count"],
            path_snapshot_json=snapshot["path_json"],
        )
        return self._build_accepted_patrol_task_response(
            task_id=task_id,
            patrol_area_id=patrol_area_id,
            area=area,
        )

    async def _async_create_accepted_patrol_task(
        self,
        cur,
        *,
        request_id,
        caregiver_id,
        patrol_area_id,
        priority,
        idempotency_key,
        area,
    ):
        snapshot = PatrolPathSnapshotBuilder.build(area)
        task_id = await self.patrol_task_repository.async_create_patrol_task_records(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            caregiver_id=caregiver_id,
            priority=priority,
            assigned_robot_id=self.runtime_config.pinky_id,
            patrol_area_id=patrol_area_id,
            patrol_area_revision=int(area["revision"]),
            patrol_area_name=area["patrol_area_name"],
            map_id=area["map_id"],
            frame_id=snapshot["frame_id"],
            waypoint_count=snapshot["waypoint_count"],
            path_snapshot_json=snapshot["path_json"],
        )
        return self._build_accepted_patrol_task_response(
            task_id=task_id,
            patrol_area_id=patrol_area_id,
            area=area,
        )

    def _build_accepted_patrol_task_response(self, *, task_id, patrol_area_id, area):
        return self.build_patrol_task_response(
            result_code="ACCEPTED",
            task_id=task_id,
            task_status="WAITING_DISPATCH",
            assigned_robot_id=self.runtime_config.pinky_id,
            patrol_area_id=patrol_area_id,
            patrol_area_name=area["patrol_area_name"],
            patrol_area_revision=int(area["revision"]),
        )

    @classmethod
    def validate_patrol_area_for_create(cls, area):
        if not area:
            return cls.build_patrol_task_response(
                result_code="REJECTED",
                result_message="요청한 patrol_area_id를 찾을 수 없습니다.",
                reason_code="PATROL_AREA_NOT_FOUND",
            )

        if not bool(area.get("is_enabled")):
            return cls.build_patrol_task_response(
                result_code="REJECTED",
                result_message="비활성화된 순찰 구역입니다.",
                reason_code="PATROL_AREA_DISABLED",
            )

        try:
            PatrolPathSnapshotBuilder.build(area)
        except ValueError as exc:
            return cls.build_patrol_task_response(
                result_code="REJECTED",
                result_message=str(exc),
                reason_code="PATROL_PATH_CONFIG_MISSING",
            )

        return None

    @staticmethod
    def _caregiver_exists(cur, caregiver_id) -> bool:
        cur.execute(
            load_sql("task_request/caregiver_exists.sql"),
            (caregiver_id,),
        )
        return cur.fetchone() is not None

    @staticmethod
    async def _async_caregiver_exists(cur, caregiver_id) -> bool:
        await cur.execute(
            load_sql("task_request/caregiver_exists.sql"),
            (caregiver_id,),
        )
        return await cur.fetchone() is not None

    def _fetch_patrol_area_by_id(self, cur, patrol_area_id):
        cur.execute(
            load_sql("task_request/find_patrol_area_by_id.sql"),
            (patrol_area_id, self.runtime_config.map_id),
        )
        return cur.fetchone()

    async def _async_fetch_patrol_area_by_id(self, cur, patrol_area_id):
        await cur.execute(
            load_sql("task_request/find_patrol_area_by_id.sql"),
            (patrol_area_id, self.runtime_config.map_id),
        )
        return await cur.fetchone()

    @staticmethod
    def _parse_numeric_identifier(value):
        raw = str(value or "").strip()
        if raw.isdigit():
            return int(raw)

        digits = "".join(ch for ch in raw if ch.isdigit())
        if not digits:
            return None
        return int(digits)

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()

    @staticmethod
    def build_patrol_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
        patrol_area_id=None,
        patrol_area_name=None,
        patrol_area_revision=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "assigned_robot_id": assigned_robot_id,
            "patrol_area_id": patrol_area_id,
            "patrol_area_name": patrol_area_name,
            "patrol_area_revision": patrol_area_revision,
        }


__all__ = [
    "PATROL_CREATE_SCOPE",
    "PatrolPathSnapshotBuilder",
    "PatrolTaskCreateRepository",
]
