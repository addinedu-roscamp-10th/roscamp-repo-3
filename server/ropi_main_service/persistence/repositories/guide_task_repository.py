import json

from server.ropi_main_service.application.guide_runtime import DEFAULT_GUIDE_PINKY_ID
from server.ropi_main_service.persistence.async_connection import async_transaction
from server.ropi_main_service.persistence.connection import get_connection
from server.ropi_main_service.persistence.repositories.idempotency_repository import (
    IdempotencyRepository,
)
from server.ropi_main_service.persistence.sql_loader import load_sql


GUIDE_CREATE_SCOPE = "GUIDE_CREATE_TASK"
GUIDE_INITIAL_PHASE = "WAIT_GUIDE_START_CONFIRM"


class GuideTaskRepository:
    def __init__(
        self,
        *,
        idempotency_repository=None,
        connection_factory=None,
        async_transaction_factory=None,
        default_pinky_id=DEFAULT_GUIDE_PINKY_ID,
    ):
        self.idempotency_repository = idempotency_repository or IdempotencyRepository()
        self.connection_factory = connection_factory or get_connection
        self.async_transaction_factory = async_transaction_factory or async_transaction
        self.default_pinky_id = str(default_pinky_id or "").strip() or DEFAULT_GUIDE_PINKY_ID

    def create_guide_task(
        self,
        *,
        request_id,
        visitor_id,
        priority="NORMAL",
        idempotency_key,
    ):
        numeric_visitor_id = self._normalize_positive_id(visitor_id)
        if numeric_visitor_id is None:
            return self.build_guide_task_response(
                result_code="INVALID_REQUEST",
                result_message="visitor_id가 올바르지 않습니다.",
                reason_code="VISITOR_ID_INVALID",
            )

        request_hash = self._build_request_hash(
            request_id=request_id,
            visitor_id=numeric_visitor_id,
            priority=priority,
        )
        conn = self.connection_factory()
        try:
            self._begin(conn)
            with conn.cursor() as cur:
                existing_response = self.idempotency_repository.find_response(
                    cur,
                    requester_type="VISITOR",
                    requester_id=str(numeric_visitor_id),
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    scope=GUIDE_CREATE_SCOPE,
                )
                if existing_response is not None:
                    conn.commit()
                    return existing_response

                response = self._create_guide_task_in_transaction(
                    cur,
                    request_id=request_id,
                    visitor_id=numeric_visitor_id,
                    priority=priority,
                    idempotency_key=idempotency_key,
                )
                self._insert_idempotency_record(
                    cur,
                    visitor_id=numeric_visitor_id,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    response=response,
                )
                conn.commit()
                return response
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def async_create_guide_task(
        self,
        *,
        request_id,
        visitor_id,
        priority="NORMAL",
        idempotency_key,
    ):
        numeric_visitor_id = self._normalize_positive_id(visitor_id)
        if numeric_visitor_id is None:
            return self.build_guide_task_response(
                result_code="INVALID_REQUEST",
                result_message="visitor_id가 올바르지 않습니다.",
                reason_code="VISITOR_ID_INVALID",
            )

        request_hash = self._build_request_hash(
            request_id=request_id,
            visitor_id=numeric_visitor_id,
            priority=priority,
        )
        async with self.async_transaction_factory() as cur:
            existing_response = await self.idempotency_repository.async_find_response(
                cur,
                requester_type="VISITOR",
                requester_id=str(numeric_visitor_id),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                scope=GUIDE_CREATE_SCOPE,
            )
            if existing_response is not None:
                return existing_response

            response = await self._async_create_guide_task_in_transaction(
                cur,
                request_id=request_id,
                visitor_id=numeric_visitor_id,
                priority=priority,
                idempotency_key=idempotency_key,
            )
            await self._async_insert_idempotency_record(
                cur,
                visitor_id=numeric_visitor_id,
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response=response,
            )
            return response

    def _build_request_hash(self, *, request_id, visitor_id, priority):
        return self.idempotency_repository.build_request_hash(
            request_id=request_id,
            visitor_id=visitor_id,
            priority=priority or "NORMAL",
        )

    def _create_guide_task_in_transaction(
        self,
        cur,
        *,
        request_id,
        visitor_id,
        priority,
        idempotency_key,
    ):
        context = self._find_visitor_guide_context(cur, visitor_id)
        guard = self._validate_context(context)
        if guard is not None:
            return guard

        destination = self._find_destination_goal_pose(cur, context["room_no"])
        guard = self._validate_destination(destination)
        if guard is not None:
            return guard

        task_id = self._insert_records(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            priority=priority,
            visitor_id=visitor_id,
            member_id=int(context["member_id"]),
            resident_name=context.get("member_name") or "-",
            room_no=context.get("room_no") or "-",
            destination_goal_pose_id=destination["goal_pose_id"],
            map_id=destination["map_id"],
        )
        return self._accepted_response(
            task_id=task_id,
            context=context,
            destination=destination,
        )

    async def _async_create_guide_task_in_transaction(
        self,
        cur,
        *,
        request_id,
        visitor_id,
        priority,
        idempotency_key,
    ):
        context = await self._async_find_visitor_guide_context(cur, visitor_id)
        guard = self._validate_context(context)
        if guard is not None:
            return guard

        destination = await self._async_find_destination_goal_pose(cur, context["room_no"])
        guard = self._validate_destination(destination)
        if guard is not None:
            return guard

        task_id = await self._async_insert_records(
            cur,
            request_id=request_id,
            idempotency_key=idempotency_key,
            priority=priority,
            visitor_id=visitor_id,
            member_id=int(context["member_id"]),
            resident_name=context.get("member_name") or "-",
            room_no=context.get("room_no") or "-",
            destination_goal_pose_id=destination["goal_pose_id"],
            map_id=destination["map_id"],
        )
        return self._accepted_response(
            task_id=task_id,
            context=context,
            destination=destination,
        )

    @staticmethod
    def _find_visitor_guide_context(cur, visitor_id):
        cur.execute(load_sql("guide/find_visitor_guide_context.sql"), (visitor_id,))
        return cur.fetchone()

    @staticmethod
    async def _async_find_visitor_guide_context(cur, visitor_id):
        await cur.execute(load_sql("guide/find_visitor_guide_context.sql"), (visitor_id,))
        return await cur.fetchone()

    @classmethod
    def _find_destination_goal_pose(cls, cur, room_no):
        cur.execute(load_sql("guide/find_destination_goal_pose.sql"), (cls._zone_id_from_room(room_no),))
        return cur.fetchone()

    @classmethod
    async def _async_find_destination_goal_pose(cls, cur, room_no):
        await cur.execute(
            load_sql("guide/find_destination_goal_pose.sql"),
            (cls._zone_id_from_room(room_no),),
        )
        return await cur.fetchone()

    def _insert_records(
        self,
        cur,
        *,
        request_id,
        idempotency_key,
        priority,
        visitor_id,
        member_id,
        resident_name,
        room_no,
        destination_goal_pose_id,
        map_id,
    ):
        cur.execute(
            load_sql("guide/insert_guide_task.sql"),
            (
                request_id,
                idempotency_key,
                str(visitor_id),
                priority or "NORMAL",
                self.default_pinky_id,
                map_id,
            ),
        )
        task_id = int(cur.lastrowid)
        self._insert_detail(
            cur,
            task_id=task_id,
            visitor_id=visitor_id,
            member_id=member_id,
            destination_goal_pose_id=destination_goal_pose_id,
        )
        self._insert_initial_history(cur, task_id=task_id)
        self._insert_initial_event(
            cur,
            task_id=task_id,
            visitor_id=visitor_id,
            member_id=member_id,
            resident_name=resident_name,
            room_no=room_no,
            destination_goal_pose_id=destination_goal_pose_id,
        )
        return task_id

    async def _async_insert_records(self, cur, **kwargs):
        await cur.execute(
            load_sql("guide/insert_guide_task.sql"),
            (
                kwargs["request_id"],
                kwargs["idempotency_key"],
                str(kwargs["visitor_id"]),
                kwargs["priority"] or "NORMAL",
                self.default_pinky_id,
                kwargs["map_id"],
            ),
        )
        task_id = int(cur.lastrowid)
        await self._async_insert_detail(
            cur,
            task_id=task_id,
            visitor_id=kwargs["visitor_id"],
            member_id=kwargs["member_id"],
            destination_goal_pose_id=kwargs["destination_goal_pose_id"],
        )
        await self._async_insert_initial_history(cur, task_id=task_id)
        await self._async_insert_initial_event(
            cur,
            task_id=task_id,
            visitor_id=kwargs["visitor_id"],
            member_id=kwargs["member_id"],
            resident_name=kwargs["resident_name"],
            room_no=kwargs["room_no"],
            destination_goal_pose_id=kwargs["destination_goal_pose_id"],
        )
        return task_id

    @staticmethod
    def _insert_detail(cur, *, task_id, visitor_id, member_id, destination_goal_pose_id):
        cur.execute(
            load_sql("guide/insert_guide_task_detail.sql"),
            (task_id, visitor_id, member_id, destination_goal_pose_id, None),
        )

    @staticmethod
    async def _async_insert_detail(cur, *, task_id, visitor_id, member_id, destination_goal_pose_id):
        await cur.execute(
            load_sql("guide/insert_guide_task_detail.sql"),
            (task_id, visitor_id, member_id, destination_goal_pose_id, None),
        )

    @staticmethod
    def _insert_initial_history(cur, *, task_id):
        cur.execute(
            load_sql("guide/insert_initial_task_history.sql"),
            (task_id, "guide task accepted", "control_service"),
        )

    @staticmethod
    async def _async_insert_initial_history(cur, *, task_id):
        await cur.execute(
            load_sql("guide/insert_initial_task_history.sql"),
            (task_id, "guide task accepted", "control_service"),
        )

    def _insert_initial_event(
        self,
        cur,
        *,
        task_id,
        visitor_id,
        member_id,
        resident_name,
        room_no,
        destination_goal_pose_id,
    ):
        cur.execute(
            load_sql("guide/insert_initial_task_event.sql"),
            (
                task_id,
                self.default_pinky_id,
                f"guide task accepted: {resident_name} / {room_no}",
                self._event_payload_json(
                    visitor_id=visitor_id,
                    member_id=member_id,
                    destination_goal_pose_id=destination_goal_pose_id,
                    room_no=room_no,
                ),
            ),
        )

    async def _async_insert_initial_event(self, cur, **kwargs):
        await cur.execute(
            load_sql("guide/insert_initial_task_event.sql"),
            (
                kwargs["task_id"],
                self.default_pinky_id,
                f"guide task accepted: {kwargs['resident_name']} / {kwargs['room_no']}",
                self._event_payload_json(
                    visitor_id=kwargs["visitor_id"],
                    member_id=kwargs["member_id"],
                    destination_goal_pose_id=kwargs["destination_goal_pose_id"],
                    room_no=kwargs["room_no"],
                ),
            ),
        )

    def _insert_idempotency_record(
        self,
        cur,
        *,
        visitor_id,
        idempotency_key,
        request_hash,
        response,
    ):
        if response.get("task_id") in (None, ""):
            return
        self.idempotency_repository.insert_record(
            cur,
            requester_type="VISITOR",
            requester_id=str(visitor_id),
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            response=response,
            task_id=response["task_id"],
            scope=GUIDE_CREATE_SCOPE,
        )

    async def _async_insert_idempotency_record(self, cur, **kwargs):
        response = kwargs["response"]
        if response.get("task_id") in (None, ""):
            return
        await self.idempotency_repository.async_insert_record(
            cur,
            requester_type="VISITOR",
            requester_id=str(kwargs["visitor_id"]),
            idempotency_key=kwargs["idempotency_key"],
            request_hash=kwargs["request_hash"],
            response=response,
            task_id=response["task_id"],
            scope=GUIDE_CREATE_SCOPE,
        )

    @classmethod
    def _validate_context(cls, context):
        if not context:
            return cls.build_guide_task_response(
                result_code="REJECTED",
                result_message="방문 등록 정보를 찾을 수 없습니다.",
                reason_code="VISITOR_NOT_FOUND",
            )
        if not context.get("member_id"):
            return cls.build_guide_task_response(
                result_code="REJECTED",
                result_message="방문자와 연결된 어르신 정보를 찾을 수 없습니다.",
                reason_code="VISITOR_RESIDENT_MAPPING_NOT_FOUND",
            )
        return None

    @classmethod
    def _validate_destination(cls, destination):
        if not destination:
            return cls.build_guide_task_response(
                result_code="REJECTED",
                result_message="안내 목적지 좌표가 설정되어 있지 않습니다.",
                reason_code="GUIDE_DESTINATION_NOT_CONFIGURED",
            )
        return None

    def _accepted_response(self, *, task_id, context, destination):
        return self.build_guide_task_response(
            result_code="ACCEPTED",
            result_message="안내 요청이 접수되었습니다.",
            task_id=task_id,
            task_status="WAITING_DISPATCH",
            phase=GUIDE_INITIAL_PHASE,
            assigned_robot_id=self.default_pinky_id,
            visitor_id=context.get("visitor_id"),
            visitor_name=context.get("visitor_name"),
            relation_name=context.get("relation_name"),
            member_id=context.get("member_id"),
            resident_name=context.get("member_name") or "-",
            room_no=context.get("room_no") or "-",
            destination_id=destination["goal_pose_id"],
            destination_map_id=destination.get("map_id"),
            destination_zone_id=destination.get("zone_id"),
            destination_zone_name=destination.get("zone_name"),
            destination_purpose=destination.get("purpose"),
        )

    @staticmethod
    def _event_payload_json(*, visitor_id, member_id, destination_goal_pose_id, room_no):
        return json.dumps(
            {
                "visitor_id": visitor_id,
                "member_id": member_id,
                "destination_id": destination_goal_pose_id,
                "room_no": room_no,
                "guide_phase": GUIDE_INITIAL_PHASE,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _normalize_positive_id(value):
        try:
            normalized = int(str(value or "").strip())
        except (TypeError, ValueError):
            return None
        if normalized <= 0:
            return None
        return normalized

    @staticmethod
    def _zone_id_from_room(room_no):
        raw = str(room_no or "").strip().lower()
        if not raw:
            return ""
        if raw.startswith("room_"):
            return raw
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits:
            return f"room_{digits}"
        return f"room_{raw.replace(' ', '_')}"

    @staticmethod
    def _begin(conn):
        if hasattr(conn, "begin"):
            conn.begin()

    @staticmethod
    def build_guide_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        phase=None,
        assigned_robot_id=None,
        visitor_id=None,
        visitor_name=None,
        relation_name=None,
        member_id=None,
        resident_name=None,
        room_no=None,
        destination_id=None,
        destination_map_id=None,
        destination_zone_id=None,
        destination_zone_name=None,
        destination_purpose=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "phase": phase,
            "assigned_robot_id": assigned_robot_id,
            "visitor_id": visitor_id,
            "visitor_name": visitor_name,
            "relation_name": relation_name,
            "member_id": member_id,
            "resident_name": resident_name,
            "room_no": room_no,
            "destination_id": destination_id,
            "destination_map_id": destination_map_id,
            "destination_zone_id": destination_zone_id,
            "destination_zone_name": destination_zone_name,
            "destination_purpose": destination_purpose,
        }


__all__ = ["GUIDE_CREATE_SCOPE", "GuideTaskRepository"]
