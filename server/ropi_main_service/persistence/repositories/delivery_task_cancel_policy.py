import json


CONTROL_SERVICE_COMPONENT = "control_service"
TASK_STATUS_CANCEL_REQUESTED = "CANCEL_REQUESTED"
TASK_STATUS_CANCELLED = "CANCELLED"
REASON_USER_CANCEL_REQUESTED = "USER_CANCEL_REQUESTED"
REASON_ROS_ACTION_CANCELLED = "ROS_ACTION_CANCELLED"
CANCELLABLE_DELIVERY_TASK_STATUSES = {
    "WAITING",
    "WAITING_DISPATCH",
    "READY",
    "ASSIGNED",
    "RUNNING",
}
CANCEL_FINALIZABLE_DELIVERY_TASK_STATUSES = {
    TASK_STATUS_CANCEL_REQUESTED,
}


class DeliveryTaskCancelPolicy:
    @classmethod
    def build_invalid_task_id_cancel_response(cls):
        return cls.build_cancel_task_response(
            result_code="REJECTED",
            result_message="task_id를 확인할 수 없습니다.",
            reason_code="TASK_ID_INVALID",
            task_id=None,
        )

    @classmethod
    def build_invalid_task_id_cancelled_response(cls, workflow_response):
        return cls.build_cancelled_task_response(
            result_code="REJECTED",
            result_message="task_id를 확인할 수 없습니다.",
            reason_code="TASK_ID_INVALID",
            task_id=None,
            workflow_response=workflow_response,
        )

    @staticmethod
    def parse_task_id(value):
        raw = str(value or "").strip()
        if not raw.isdigit():
            return None
        return int(raw)

    @staticmethod
    def is_cancellable_task_status(task_status):
        return str(task_status or "").strip() in CANCELLABLE_DELIVERY_TASK_STATUSES

    @classmethod
    def build_cancel_target_response(cls, row, *, task_id):
        if not row:
            return cls.build_cancel_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )

        if not cls.is_cancellable_task_status(row.get("task_status")):
            return cls.build_cancel_task_response(
                result_code="REJECTED",
                result_message="이미 종료되었거나 취소할 수 없는 운반 task입니다.",
                reason_code="TASK_NOT_CANCELLABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )

        return cls.build_cancel_task_response(
            result_code="ACCEPTED",
            task_id=row.get("task_id"),
            task_status=row.get("task_status"),
            assigned_robot_id=row.get("assigned_robot_id"),
        )

    def build_cancel_result_guard(self, row, *, task_id):
        if not row:
            return self.build_cancel_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
            )

        if not self.is_cancellable_task_status(row.get("task_status")):
            return self.build_cancel_task_response(
                result_code="REJECTED",
                result_message="이미 종료되었거나 취소할 수 없는 운반 task입니다.",
                reason_code="TASK_NOT_CANCELLABLE",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
            )

        return None

    def build_cancelled_result_guard(self, row, *, task_id, workflow_response):
        if not row:
            return self.build_cancelled_task_response(
                result_code="REJECTED",
                result_message="운반 task를 찾을 수 없습니다.",
                reason_code="TASK_NOT_FOUND",
                task_id=task_id,
                workflow_response=workflow_response,
            )

        if str(row.get("task_status") or "").strip() == TASK_STATUS_CANCELLED:
            return self.build_cancelled_task_response(
                result_code=TASK_STATUS_CANCELLED,
                result_message="운반 task가 이미 취소 완료 상태입니다.",
                reason_code="ALREADY_CANCELLED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                workflow_response=workflow_response,
            )

        if str(row.get("task_status") or "").strip() not in CANCEL_FINALIZABLE_DELIVERY_TASK_STATUSES:
            return self.build_cancelled_task_response(
                result_code="IGNORED",
                result_message="취소 요청 상태가 아니므로 취소 완료로 확정하지 않았습니다.",
                reason_code="TASK_NOT_CANCEL_REQUESTED",
                task_id=row.get("task_id"),
                task_status=row.get("task_status"),
                assigned_robot_id=row.get("assigned_robot_id"),
                workflow_response=workflow_response,
            )

        return None

    def build_cancel_result_write_plan(self, *, row, cancel_response):
        result_code, result_message, reason_code = self.normalize_cancel_result(cancel_response)
        cancel_requested = bool((cancel_response or {}).get("cancel_requested"))
        task_status = row.get("task_status")
        event_name = "DELIVERY_TASK_CANCEL_REJECTED"
        severity = "WARNING"
        update_params = None
        history_params = None

        if cancel_requested:
            task_status = TASK_STATUS_CANCEL_REQUESTED
            event_name = "DELIVERY_TASK_CANCEL_REQUESTED"
            severity = "INFO"
            update_params = (
                REASON_USER_CANCEL_REQUESTED,
                result_code,
                result_message,
                row["task_id"],
            )
            history_params = (
                row["task_id"],
                row.get("task_status"),
                row.get("phase"),
                REASON_USER_CANCEL_REQUESTED,
                result_message,
                CONTROL_SERVICE_COMPONENT,
            )

        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_status": task_status,
            "cancel_requested": cancel_requested,
            "update_params": update_params,
            "history_params": history_params,
            "event_params": self.build_task_event_params(
                row=row,
                event_name=event_name,
                severity=severity,
                result_code=result_code,
                reason_code=reason_code,
                result_message=result_message,
                payload=cancel_response,
            ),
        }

    def build_cancelled_result_write_plan(self, *, row, workflow_response):
        result_code, result_message, reason_code = self.normalize_cancelled_workflow_result(workflow_response)
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_status": TASK_STATUS_CANCELLED,
            "update_params": (
                reason_code,
                result_code,
                result_message,
                row["task_id"],
            ),
            "history_params": (
                row["task_id"],
                row.get("task_status"),
                row.get("phase"),
                reason_code,
                result_message,
                CONTROL_SERVICE_COMPONENT,
            ),
            "event_params": self.build_task_event_params(
                row=row,
                event_name="DELIVERY_TASK_CANCELLED",
                severity="INFO",
                result_code=result_code,
                reason_code=reason_code,
                result_message=result_message,
                payload=workflow_response,
            ),
        }

    @staticmethod
    def build_task_event_params(
        *,
        row,
        event_name,
        severity,
        result_code,
        reason_code,
        result_message,
        payload,
    ):
        return (
            row["task_id"],
            event_name,
            severity,
            row.get("assigned_robot_id"),
            result_code,
            reason_code,
            result_message,
            json.dumps(payload or {}, ensure_ascii=False),
        )

    @staticmethod
    def normalize_cancel_result(cancel_response):
        cancel_response = cancel_response or {}
        result_code = str(cancel_response.get("result_code") or "UNKNOWN").strip() or "UNKNOWN"
        result_message = cancel_response.get("result_message")
        if result_message is None:
            result_message = (
                "운반 task 취소 요청이 접수되었습니다."
                if cancel_response.get("cancel_requested")
                else "운반 task 취소 요청이 수락되지 않았습니다."
            )
        reason_code = cancel_response.get("reason_code")
        if reason_code is None:
            reason_code = (
                REASON_USER_CANCEL_REQUESTED
                if cancel_response.get("cancel_requested")
                else "ROS_CANCEL_NOT_ACCEPTED"
            )
        return result_code, result_message, reason_code

    @staticmethod
    def normalize_cancelled_workflow_result(workflow_response):
        workflow_response = workflow_response or {}
        result_message = workflow_response.get("result_message") or "운반 task가 취소 완료되었습니다."
        return TASK_STATUS_CANCELLED, result_message, REASON_ROS_ACTION_CANCELLED

    @staticmethod
    def build_delivery_task_response(
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
    ):
        return {
            "result_code": result_code,
            "result_message": result_message,
            "reason_code": reason_code,
            "task_id": task_id,
            "task_status": task_status,
            "assigned_robot_id": assigned_robot_id,
        }

    @classmethod
    def build_cancel_task_response(
        cls,
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
        cancel_requested=None,
        ros_result=None,
    ):
        response = cls.build_delivery_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=task_id,
            task_status=task_status,
            assigned_robot_id=assigned_robot_id,
        )
        if cancel_requested is not None:
            response["cancel_requested"] = cancel_requested
        if ros_result is not None:
            response["ros_result"] = ros_result
        return response

    @classmethod
    def build_cancelled_task_response(
        cls,
        *,
        result_code,
        result_message=None,
        reason_code=None,
        task_id=None,
        task_status=None,
        assigned_robot_id=None,
        workflow_response=None,
    ):
        response = cls.build_delivery_task_response(
            result_code=result_code,
            result_message=result_message,
            reason_code=reason_code,
            task_id=task_id,
            task_status=task_status,
            assigned_robot_id=assigned_robot_id,
        )
        if workflow_response is not None:
            response["workflow_result"] = workflow_response
        return response


__all__ = [
    "DeliveryTaskCancelPolicy",
]
