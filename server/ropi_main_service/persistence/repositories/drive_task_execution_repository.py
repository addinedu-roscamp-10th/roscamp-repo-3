import json

from server.ropi_main_service.persistence.async_connection import async_transaction
from server.ropi_main_service.persistence.sql_loader import load_sql


CONTROL_SERVICE_COMPONENT = "control_service"
DRIVE_EXECUTION_START_MESSAGE = "DRIVE task execution started."
DRIVE_RESERVATION_WAITING_MESSAGE = "DRIVE task is waiting for FMS reservation."
TASK_STATUS_RUNNING = "RUNNING"
TASK_STATUS_WAITING_DISPATCH = "WAITING_DISPATCH"
TASK_STATUS_CANCEL_REQUESTED = "CANCEL_REQUESTED"
TASK_STATUS_COMPLETED = "COMPLETED"
TASK_STATUS_CANCELLED = "CANCELLED"
TASK_STATUS_FAILED = "FAILED"
PHASE_FOLLOW_DRIVE_ROUTE = "FOLLOW_DRIVE_ROUTE"
PHASE_WAITING_FMS_RESERVATION = "WAITING_FMS_RESERVATION"
DRIVE_STATUS_MOVING = "MOVING"
DRIVE_STATUS_WAITING_FMS_RESERVATION = "WAITING_FMS_RESERVATION"
DRIVE_WORKFLOW_FAILED_REASON = "DRIVE_WORKFLOW_FAILED"
DRIVE_WORKFLOW_CANCELLED_REASON = "DRIVE_WORKFLOW_CANCELLED"
TERMINAL_DRIVE_TASK_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}
STARTABLE_DRIVE_TASK_STATUSES = {"WAITING_DISPATCH", "RUNNING"}


class DriveTaskExecutionRepository:
    async def async_get_drive_execution_snapshot(self, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return None

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("drive/get_drive_execution_snapshot.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            if not row:
                return None

            await cur.execute(
                load_sql("drive/list_drive_route_edges.sql"),
                (numeric_task_id,),
            )
            edge_rows = await cur.fetchall()

        snapshot = dict(row)
        snapshot["path_snapshot_json"] = self._parse_path_snapshot(
            snapshot.get("path_snapshot_json")
        )
        snapshot["reservation_resources"] = self._build_reservation_resources(
            path_snapshot=snapshot["path_snapshot_json"],
            edge_rows=edge_rows,
        )
        return snapshot

    async def async_record_drive_reservation_waiting(
        self,
        *,
        task_id,
        reservation_response,
    ):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_drive_state_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
                task_status=None,
                phase=None,
                assigned_robot_id=None,
                cancellable=False,
            )

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("drive/lock_drive_task_for_start.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            guard_response = self._build_start_guard(row, task_id=numeric_task_id)
            if guard_response is not None:
                return guard_response

            reason_code = (
                reservation_response.get("reason_code")
                or "FMS_RESOURCE_ALREADY_HELD"
            )
            message = reservation_response.get("result_message") or (
                DRIVE_RESERVATION_WAITING_MESSAGE
            )
            await cur.execute(
                load_sql("drive/update_drive_task_reservation_waiting.sql"),
                (reason_code, message, numeric_task_id),
            )
            await cur.execute(
                load_sql("drive/update_drive_task_detail_reservation_waiting.sql"),
                (numeric_task_id,),
            )
            await cur.execute(
                load_sql("drive/insert_task_runtime_history.sql"),
                (
                    numeric_task_id,
                    row.get("task_status"),
                    TASK_STATUS_WAITING_DISPATCH,
                    row.get("phase"),
                    PHASE_WAITING_FMS_RESERVATION,
                    reason_code,
                    message,
                    CONTROL_SERVICE_COMPONENT,
                ),
            )
            await cur.execute(
                load_sql("drive/insert_task_runtime_event.sql"),
                (
                    numeric_task_id,
                    "DRIVE_FMS_RESERVATION_WAITING",
                    "INFO",
                    row.get("assigned_robot_id"),
                    "WAITING",
                    reason_code,
                    message,
                    json.dumps(reservation_response or {}, ensure_ascii=False),
                ),
            )

        return self._build_drive_state_response(
            result_code="ACCEPTED",
            result_message=message,
            reason_code=reason_code,
            task_id=numeric_task_id,
            task_status=TASK_STATUS_WAITING_DISPATCH,
            phase=PHASE_WAITING_FMS_RESERVATION,
            assigned_robot_id=row.get("assigned_robot_id"),
            cancellable=True,
        )

    async def async_record_drive_execution_started(self, task_id):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_drive_state_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
                task_status=None,
                phase=None,
                assigned_robot_id=None,
                cancellable=False,
            )

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("drive/lock_drive_task_for_start.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            guard_response = self._build_start_guard(row, task_id=numeric_task_id)
            if guard_response is not None:
                return guard_response

            await cur.execute(
                load_sql("drive/update_drive_task_started.sql"),
                ("ACCEPTED", DRIVE_EXECUTION_START_MESSAGE, numeric_task_id),
            )
            await cur.execute(
                load_sql("drive/update_drive_task_detail_started.sql"),
                (DRIVE_STATUS_MOVING, 0, numeric_task_id),
            )
            await cur.execute(
                load_sql("drive/insert_task_runtime_history.sql"),
                (
                    numeric_task_id,
                    row.get("task_status"),
                    TASK_STATUS_RUNNING,
                    row.get("phase"),
                    PHASE_FOLLOW_DRIVE_ROUTE,
                    None,
                    DRIVE_EXECUTION_START_MESSAGE,
                    CONTROL_SERVICE_COMPONENT,
                ),
            )
            await cur.execute(
                load_sql("drive/insert_task_runtime_event.sql"),
                (
                    numeric_task_id,
                    "DRIVE_TASK_STARTED",
                    "INFO",
                    row.get("assigned_robot_id"),
                    "ACCEPTED",
                    None,
                    DRIVE_EXECUTION_START_MESSAGE,
                    json.dumps(
                        {
                            "task_id": numeric_task_id,
                            "assigned_robot_id": row.get("assigned_robot_id"),
                            "phase": PHASE_FOLLOW_DRIVE_ROUTE,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )

        return self._build_drive_state_response(
            result_code="ACCEPTED",
            result_message=DRIVE_EXECUTION_START_MESSAGE,
            reason_code=None,
            task_id=numeric_task_id,
            task_status=TASK_STATUS_RUNNING,
            phase=PHASE_FOLLOW_DRIVE_ROUTE,
            assigned_robot_id=row.get("assigned_robot_id"),
            cancellable=True,
        )

    async def async_record_drive_task_workflow_result(
        self,
        *,
        task_id,
        workflow_response,
    ):
        numeric_task_id = self._parse_task_id(task_id)
        if numeric_task_id is None:
            return self._build_drive_state_response(
                result_code="REJECTED",
                result_message="task_id를 확인할 수 없습니다.",
                reason_code="TASK_ID_INVALID",
                task_id=None,
                task_status=None,
                phase=None,
                assigned_robot_id=None,
                cancellable=False,
            )

        async with async_transaction() as cur:
            await cur.execute(
                load_sql("drive/lock_drive_task_for_result.sql"),
                (numeric_task_id,),
            )
            row = await cur.fetchone()
            if not row:
                return self._build_drive_state_response(
                    result_code="NOT_FOUND",
                    result_message="DRIVE task 실행 정보를 찾을 수 없습니다.",
                    reason_code="DRIVE_TASK_NOT_FOUND",
                    task_id=numeric_task_id,
                    task_status=None,
                    phase=None,
                    assigned_robot_id=None,
                    cancellable=False,
                )

            normalized = self._normalize_workflow_result(workflow_response)
            await cur.execute(
                load_sql("drive/update_drive_task_workflow_result.sql"),
                (
                    normalized["task_status"],
                    normalized["phase"],
                    normalized["reason_code"],
                    normalized["result_code"],
                    normalized["result_message"],
                    numeric_task_id,
                ),
            )
            await cur.execute(
                load_sql("drive/update_drive_task_detail_result.sql"),
                (
                    normalized["drive_status"],
                    row.get("waypoint_count"),
                    numeric_task_id,
                ),
            )
            await cur.execute(
                load_sql("drive/insert_task_runtime_history.sql"),
                (
                    numeric_task_id,
                    row.get("task_status"),
                    normalized["task_status"],
                    row.get("phase"),
                    normalized["phase"],
                    normalized["reason_code"],
                    normalized["result_message"],
                    CONTROL_SERVICE_COMPONENT,
                ),
            )
            await cur.execute(
                load_sql("drive/insert_task_runtime_event.sql"),
                (
                    numeric_task_id,
                    normalized["event_name"],
                    normalized["severity"],
                    row.get("assigned_robot_id"),
                    normalized["result_code"],
                    normalized["reason_code"],
                    normalized["result_message"],
                    json.dumps(workflow_response or {}, ensure_ascii=False),
                ),
            )

        return self._build_drive_state_response(
            result_code=normalized["result_code"],
            result_message=normalized["result_message"],
            reason_code=normalized["reason_code"],
            task_id=numeric_task_id,
            task_status=normalized["task_status"],
            phase=normalized["phase"],
            assigned_robot_id=row.get("assigned_robot_id"),
            cancellable=False,
        )

    def _build_start_guard(self, row, *, task_id):
        if not row:
            return self._build_drive_state_response(
                result_code="NOT_FOUND",
                result_message="DRIVE task 실행 정보를 찾을 수 없습니다.",
                reason_code="DRIVE_TASK_NOT_FOUND",
                task_id=task_id,
                task_status=None,
                phase=None,
                assigned_robot_id=None,
                cancellable=False,
            )

        task_status = str(row.get("task_status") or "").strip().upper()
        if task_status in TERMINAL_DRIVE_TASK_STATUSES:
            return self._build_drive_state_response(
                result_code="NOT_ALLOWED",
                result_message="이미 종료된 DRIVE task는 실행할 수 없습니다.",
                reason_code="DRIVE_TASK_ALREADY_TERMINAL",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
                cancellable=False,
            )

        if task_status == TASK_STATUS_RUNNING:
            return self._build_drive_state_response(
                result_code="ACCEPTED",
                result_message=DRIVE_EXECUTION_START_MESSAGE,
                reason_code=None,
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase") or PHASE_FOLLOW_DRIVE_ROUTE,
                assigned_robot_id=row.get("assigned_robot_id"),
                cancellable=True,
            )

        if task_status == TASK_STATUS_CANCEL_REQUESTED:
            return self._build_drive_state_response(
                result_code="CANCELLED",
                result_message="DRIVE task 취소 요청으로 주행을 시작하지 않습니다.",
                reason_code="DRIVE_TASK_CANCEL_REQUESTED",
                task_id=row.get("task_id"),
                task_status=TASK_STATUS_CANCELLED,
                phase=TASK_STATUS_CANCELLED,
                assigned_robot_id=row.get("assigned_robot_id"),
                cancellable=False,
            )

        if task_status not in STARTABLE_DRIVE_TASK_STATUSES:
            return self._build_drive_state_response(
                result_code="NOT_ALLOWED",
                result_message="DRIVE task를 실행할 수 없는 상태입니다.",
                reason_code="DRIVE_TASK_NOT_STARTABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                phase=row.get("phase"),
                assigned_robot_id=row.get("assigned_robot_id"),
                cancellable=False,
            )

        return None

    @staticmethod
    def _build_reservation_resources(*, path_snapshot, edge_rows):
        resources = []
        seen = set()
        poses = path_snapshot.get("poses") if isinstance(path_snapshot, dict) else []
        edges_by_sequence = {}
        for row in edge_rows or []:
            try:
                sequence_no = int(row.get("from_sequence_no") or 0)
            except (TypeError, ValueError):
                continue
            edges_by_sequence.setdefault(sequence_no, []).append(row)

        for index, pose in enumerate(poses or [], start=1):
            waypoint_id = str((pose or {}).get("waypoint_id") or "").strip()
            key = ("WAYPOINT", waypoint_id)
            if waypoint_id and key not in seen:
                resources.append(
                    {"resource_type": "WAYPOINT", "resource_id": waypoint_id}
                )
                seen.add(key)

            sequence_no = pose.get("sequence_no") if isinstance(pose, dict) else index
            try:
                sequence_no = int(sequence_no or index)
            except (TypeError, ValueError):
                sequence_no = index
            for row in edges_by_sequence.get(sequence_no, []):
                edge_id = str(row.get("edge_id") or "").strip()
                key = ("EDGE", edge_id)
                if edge_id and key not in seen:
                    resources.append({"resource_type": "EDGE", "resource_id": edge_id})
                    seen.add(key)

        return resources

    @staticmethod
    def _parse_task_id(value):
        raw = str(value or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    @staticmethod
    def _parse_path_snapshot(value):
        if isinstance(value, str):
            return json.loads(value)
        return value

    @staticmethod
    def _normalize_workflow_result(workflow_response):
        workflow_response = workflow_response if isinstance(workflow_response, dict) else {}
        result_code = str(
            workflow_response.get("result_code") or "FAILED"
        ).strip().upper() or "FAILED"
        result_message = workflow_response.get("result_message")
        reason_code = workflow_response.get("reason_code")

        if result_code in {"SUCCEEDED", "SUCCESS"}:
            return {
                "task_status": TASK_STATUS_COMPLETED,
                "phase": TASK_STATUS_COMPLETED,
                "drive_status": TASK_STATUS_COMPLETED,
                "event_name": "DRIVE_TASK_COMPLETED",
                "severity": "INFO",
                "result_code": "SUCCEEDED",
                "reason_code": reason_code,
                "result_message": result_message or "DRIVE task가 완료되었습니다.",
            }

        if result_code in {"CANCELED", "CANCELLED"}:
            return {
                "task_status": TASK_STATUS_CANCELLED,
                "phase": TASK_STATUS_CANCELLED,
                "drive_status": TASK_STATUS_CANCELLED,
                "event_name": "DRIVE_TASK_CANCELLED",
                "severity": "WARNING",
                "result_code": result_code,
                "reason_code": reason_code or DRIVE_WORKFLOW_CANCELLED_REASON,
                "result_message": result_message or "DRIVE task가 취소되었습니다.",
            }

        return {
            "task_status": TASK_STATUS_FAILED,
            "phase": TASK_STATUS_FAILED,
            "drive_status": TASK_STATUS_FAILED,
            "event_name": "DRIVE_TASK_FAILED",
            "severity": "ERROR",
            "result_code": result_code,
            "reason_code": reason_code or DRIVE_WORKFLOW_FAILED_REASON,
            "result_message": result_message or "DRIVE task가 실패했습니다.",
        }

    @staticmethod
    def _build_drive_state_response(
        *,
        result_code,
        result_message,
        reason_code,
        task_id,
        task_status,
        phase,
        assigned_robot_id,
        cancellable,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "phase": phase,
            "assigned_robot_id": assigned_robot_id,
            "cancellable": cancellable,
        }


__all__ = ["DriveTaskExecutionRepository"]
