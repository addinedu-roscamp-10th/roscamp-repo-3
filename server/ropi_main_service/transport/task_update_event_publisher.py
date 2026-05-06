class TaskUpdateEventPublisher:
    def __init__(self, *, publish_event):
        self.publish_event = publish_event

    async def publish_from_response(self, response, *, source, task_type=None):
        payload = self.build_payload(response, source=source, task_type=task_type)
        if payload is None:
            return

        await self.publish_event("TASK_UPDATED", payload)

    @classmethod
    def build_payload(cls, response, *, source, task_type=None):
        if not isinstance(response, dict):
            return None

        task_id = response.get("task_id")
        if task_id in (None, ""):
            return None

        cancellable = response.get("cancellable")
        resolved_task_type = task_type or response.get("task_type") or "DELIVERY"
        if resolved_task_type in {"GUIDE", "PATROL"} and cancellable is None:
            cancellable = False

        payload = {
            "source": source,
            "task_id": task_id,
            "task_type": resolved_task_type,
            "task_status": response.get("task_status"),
            "phase": response.get("phase") or response.get("task_status"),
            "assigned_robot_id": response.get("assigned_robot_id"),
            "latest_reason_code": response.get("reason_code"),
            "result_code": response.get("result_code"),
            "result_message": response.get("result_message"),
            "cancel_requested": response.get("cancel_requested"),
            "cancellable": cancellable,
        }
        if resolved_task_type == "GUIDE":
            payload["guide_detail"] = cls.build_guide_detail(response)

        return payload

    @staticmethod
    def build_guide_detail(response):
        guide_detail = response.get("guide_detail")
        if isinstance(guide_detail, dict):
            return dict(guide_detail)

        return {
            "guide_phase": response.get("guide_phase") or response.get("phase"),
            "target_track_id": response.get("target_track_id"),
            "visitor_id": response.get("visitor_id"),
            "visitor_name": response.get("visitor_name"),
            "relation_name": response.get("relation_name"),
            "member_id": response.get("member_id"),
            "resident_name": response.get("resident_name") or response.get("member_name"),
            "room_no": response.get("room_no"),
            "destination_id": response.get("destination_id")
            or response.get("destination_goal_pose_id"),
            "destination_map_id": response.get("destination_map_id"),
            "destination_zone_id": response.get("destination_zone_id"),
            "destination_zone_name": response.get("destination_zone_name"),
            "destination_purpose": response.get("destination_purpose"),
        }


__all__ = ["TaskUpdateEventPublisher"]
