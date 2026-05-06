from server.ropi_main_service.application.action_feedback import (
    RosActionFeedbackService,
)
from server.ropi_main_service.application.caregiver import CaregiverService


class CaregiverRpcFacade:
    def __init__(self, *, service=None, action_feedback_service=None):
        self.service = service or CaregiverService()
        self.action_feedback_service = (
            action_feedback_service or RosActionFeedbackService()
        )

    def get_dashboard_bundle(self):
        flow_data = self.service.get_flow_board_data()
        self._attach_action_feedback(flow_data)
        return {
            "summary": self.service.get_dashboard_summary(),
            "robots": self.service.get_robot_board_data(),
            "flow_data": flow_data,
            "timeline_rows": self.service.get_timeline_data(),
        }

    async def async_get_dashboard_bundle(self):
        flow_data = await self.service.async_get_flow_board_data()
        await self._async_attach_action_feedback(flow_data)
        return {
            "summary": await self.service.async_get_dashboard_summary(),
            "robots": await self.service.async_get_robot_board_data(),
            "flow_data": flow_data,
            "timeline_rows": await self.service.async_get_timeline_data(),
        }

    def get_robot_status_bundle(self):
        return self.service.get_robot_status_bundle()

    async def async_get_robot_status_bundle(self):
        return await self.service.async_get_robot_status_bundle()

    def get_alert_log_bundle(self, **filters):
        return self.service.get_alert_log_bundle(**filters)

    async def async_get_alert_log_bundle(self, **filters):
        return await self.service.async_get_alert_log_bundle(**filters)

    def _attach_action_feedback(self, flow_data):
        for task in self._iter_feedback_target_tasks(flow_data):
            task_id = task.get("task_id")
            if not task_id:
                continue

            try:
                response = self.action_feedback_service.get_latest_feedback(
                    task_id=task_id,
                )
            except Exception:
                continue

            self._apply_feedback_response(task, response)

    async def _async_attach_action_feedback(self, flow_data):
        for task in self._iter_feedback_target_tasks(flow_data):
            task_id = task.get("task_id")
            if not task_id:
                continue

            try:
                response = (
                    await self.action_feedback_service.async_get_latest_feedback(
                        task_id=task_id,
                    )
                )
            except Exception:
                continue

            self._apply_feedback_response(task, response)

    @staticmethod
    def _iter_feedback_target_tasks(flow_data):
        for column_key in ("IN_PROGRESS", "CANCELING", "RUNNING"):
            for task in flow_data.get(column_key, []):
                if not isinstance(task, dict):
                    continue
                if task.get("task_status") not in ("RUNNING", "CANCEL_REQUESTED"):
                    continue
                yield task

    @classmethod
    def _apply_feedback_response(cls, task, response):
        feedback_records = response.get("feedback") or []
        if not feedback_records:
            return

        feedback = feedback_records[0]
        task["feedback"] = feedback
        task["feedback_summary"] = cls._build_feedback_summary(feedback)

    @staticmethod
    def _build_feedback_summary(feedback):
        payload = feedback.get("payload") or {}
        feedback_type = feedback.get("feedback_type")

        if feedback_type == "NAVIGATION_FEEDBACK":
            nav_status = payload.get("nav_status") or "NAVIGATION"
            distance = payload.get("distance_remaining_m")
            if distance is None:
                return str(nav_status)
            return f"{nav_status} / 남은 거리 {float(distance):.2f}m"

        if feedback_type == "MANIPULATION_FEEDBACK":
            processed_quantity = payload.get("processed_quantity")
            if processed_quantity is None:
                return "로봇팔 작업 중"
            return f"처리 수량 {processed_quantity}"

        return str(feedback_type or "ACTION_FEEDBACK")


__all__ = ["CaregiverRpcFacade"]
