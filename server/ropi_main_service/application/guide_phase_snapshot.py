import asyncio

from server.ropi_main_service.application.delivery_config import (
    get_delivery_runtime_config,
)
from server.ropi_main_service.application.goal_pose_navigation import (
    GoalPoseNavigationService,
)
from server.ropi_main_service.persistence.repositories.guide_phase_snapshot_repository import (
    GuidePhaseSnapshotRepository,
)


RETURN_TO_DOCK_NAV_PHASE = "RETURN_TO_DOCK"
TERMINAL_FINISHED_PHASE = "GUIDANCE_FINISHED"
DEFAULT_RETURN_TO_DOCK_TIMEOUT_SEC = 120


class GuidePhaseSnapshotProcessor:
    def __init__(
        self,
        *,
        guide_phase_snapshot_repository=None,
        goal_pose_navigation_service=None,
        return_to_dock_goal_pose_resolver=None,
        return_to_dock_timeout_sec=DEFAULT_RETURN_TO_DOCK_TIMEOUT_SEC,
    ):
        self.guide_phase_snapshot_repository = (
            guide_phase_snapshot_repository or GuidePhaseSnapshotRepository()
        )
        self.goal_pose_navigation_service = (
            goal_pose_navigation_service or GoalPoseNavigationService()
        )
        self.return_to_dock_goal_pose_resolver = (
            return_to_dock_goal_pose_resolver or self._default_return_to_dock_goal_pose
        )
        self.return_to_dock_timeout_sec = int(return_to_dock_timeout_sec)
        self._latest_seq_by_stream = {}
        self._return_dispatched_task_ids = set()

    def process(self, snapshot):
        normalized = self._normalize_snapshot(snapshot)
        stale_response = self._mark_seq_or_build_stale_response(normalized)
        if stale_response is not None:
            return stale_response

        response = self.guide_phase_snapshot_repository.record_phase_snapshot(
            **normalized
        )
        self._maybe_dispatch_return_to_dock(normalized=normalized, response=response)
        return response

    async def async_process(self, snapshot):
        normalized = self._normalize_snapshot(snapshot)
        stale_response = self._mark_seq_or_build_stale_response(normalized)
        if stale_response is not None:
            return stale_response

        async_record = getattr(
            self.guide_phase_snapshot_repository,
            "async_record_phase_snapshot",
            None,
        )
        if async_record is not None:
            response = await async_record(**normalized)
        else:
            response = await asyncio.to_thread(
                self.guide_phase_snapshot_repository.record_phase_snapshot,
                **normalized,
            )
        await self._async_maybe_dispatch_return_to_dock(
            normalized=normalized,
            response=response,
        )
        return response

    def _maybe_dispatch_return_to_dock(self, *, normalized, response):
        if not self._should_dispatch_return_to_dock(normalized=normalized, response=response):
            return

        task_id = response.get("task_id") or normalized["task_id"]
        if task_id in self._return_dispatched_task_ids:
            return
        self._return_dispatched_task_ids.add(task_id)

        goal_pose = self.return_to_dock_goal_pose_resolver()
        if not goal_pose:
            response["return_to_dock_response"] = {
                "result_code": "REJECTED",
                "reason_code": "RETURN_TO_DOCK_GOAL_POSE_MISSING",
                "result_message": "return_to_dock goal pose를 찾을 수 없습니다.",
            }
            return

        response["return_to_dock_response"] = self.goal_pose_navigation_service.navigate(
            task_id=task_id,
            pinky_id=response.get("assigned_robot_id") or normalized["pinky_id"],
            nav_phase=RETURN_TO_DOCK_NAV_PHASE,
            goal_pose=goal_pose,
            timeout_sec=self.return_to_dock_timeout_sec,
        )

    async def _async_maybe_dispatch_return_to_dock(self, *, normalized, response):
        if not self._should_dispatch_return_to_dock(normalized=normalized, response=response):
            return

        task_id = response.get("task_id") or normalized["task_id"]
        if task_id in self._return_dispatched_task_ids:
            return
        self._return_dispatched_task_ids.add(task_id)

        goal_pose = self.return_to_dock_goal_pose_resolver()
        if not goal_pose:
            response["return_to_dock_response"] = {
                "result_code": "REJECTED",
                "reason_code": "RETURN_TO_DOCK_GOAL_POSE_MISSING",
                "result_message": "return_to_dock goal pose를 찾을 수 없습니다.",
            }
            return

        async_navigate = getattr(
            self.goal_pose_navigation_service,
            "async_navigate",
            None,
        )
        kwargs = {
            "task_id": task_id,
            "pinky_id": response.get("assigned_robot_id") or normalized["pinky_id"],
            "nav_phase": RETURN_TO_DOCK_NAV_PHASE,
            "goal_pose": goal_pose,
            "timeout_sec": self.return_to_dock_timeout_sec,
        }
        if async_navigate is not None:
            response["return_to_dock_response"] = await async_navigate(**kwargs)
            return

        response["return_to_dock_response"] = await asyncio.to_thread(
            self.goal_pose_navigation_service.navigate,
            **kwargs,
        )

    @staticmethod
    def _should_dispatch_return_to_dock(*, normalized, response):
        if normalized.get("guide_phase") != TERMINAL_FINISHED_PHASE:
            return False
        return (
            (response or {}).get("result_code") == "ACCEPTED"
            and (response or {}).get("task_status") == "COMPLETED"
            and (response or {}).get("phase") == TERMINAL_FINISHED_PHASE
        )

    def _mark_seq_or_build_stale_response(self, normalized):
        stream_key = (normalized["task_id"], normalized["pinky_id"])
        seq = normalized["seq"]
        latest_seq = self._latest_seq_by_stream.get(stream_key)
        if latest_seq is not None and seq <= latest_seq:
            return {
                "result_code": "IGNORED",
                "result_message": "stale guide phase snapshot ignored.",
                "reason_code": "STALE_GUIDE_PHASE_SNAPSHOT",
                "task_id": normalized["task_id"],
                "task_type": "GUIDE",
                "assigned_robot_id": normalized["pinky_id"],
                "guide_phase": normalized["guide_phase"],
                "target_track_id": normalized["target_track_id"],
            }
        self._latest_seq_by_stream[stream_key] = seq
        return None

    @staticmethod
    def _normalize_snapshot(snapshot):
        snapshot = snapshot or {}
        return {
            "task_id": str(snapshot.get("task_id") or "").strip(),
            "pinky_id": str(snapshot.get("pinky_id") or "").strip(),
            "guide_phase": str(snapshot.get("guide_phase") or "").strip().upper(),
            "target_track_id": GuidePhaseSnapshotProcessor._normalize_int(
                snapshot.get("target_track_id"),
                default=-1,
            ),
            "reason_code": str(snapshot.get("reason_code") or "").strip().upper(),
            "seq": GuidePhaseSnapshotProcessor._normalize_int(
                snapshot.get("seq"),
                default=0,
            ),
            "occurred_at": snapshot.get("occurred_at"),
        }

    @staticmethod
    def _normalize_int(value, *, default):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _default_return_to_dock_goal_pose():
        return (get_delivery_runtime_config().return_to_dock_goal_pose or {})


__all__ = [
    "GuidePhaseSnapshotProcessor",
    "RETURN_TO_DOCK_NAV_PHASE",
]
