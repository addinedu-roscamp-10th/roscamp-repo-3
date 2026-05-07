import asyncio

from server.ropi_main_service.application.guide_phase_snapshot import (
    GuidePhaseSnapshotProcessor,
)


class FakeGuidePhaseSnapshotRepository:
    def __init__(self, response=None):
        self.response = response or {
            "result_code": "ACCEPTED",
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "READY_TO_START_GUIDANCE",
            "guide_phase": "READY_TO_START_GUIDANCE",
            "assigned_robot_id": "pinky1",
            "target_track_id": 17,
        }
        self.recorded = []

    def record_phase_snapshot(self, **kwargs):
        self.recorded.append(kwargs)
        return dict(self.response)

    async def async_record_phase_snapshot(self, **kwargs):
        self.recorded.append(kwargs)
        return dict(self.response)


class FakeGoalPoseNavigationService:
    def __init__(self, response=None):
        self.response = response or {"result_code": "ACCEPTED", "nav_phase": "RETURN_TO_DOCK"}
        self.navigated = []

    def navigate(self, **kwargs):
        self.navigated.append(kwargs)
        return dict(self.response)

    async def async_navigate(self, **kwargs):
        self.navigated.append(kwargs)
        return dict(self.response)


def _dock_pose():
    return {
        "header": {"frame_id": "map"},
        "pose": {
            "position": {"x": 0.5, "y": 0.5, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }


def test_processor_records_ready_to_start_snapshot_without_return_to_dock():
    repository = FakeGuidePhaseSnapshotRepository()
    navigation = FakeGoalPoseNavigationService()
    processor = GuidePhaseSnapshotProcessor(
        guide_phase_snapshot_repository=repository,
        goal_pose_navigation_service=navigation,
        return_to_dock_goal_pose_resolver=_dock_pose,
    )

    response = processor.process(
        {
            "task_id": "3001",
            "pinky_id": "pinky1",
            "guide_phase": "READY_TO_START_GUIDANCE",
            "target_track_id": 17,
            "reason_code": "",
            "seq": 42,
        }
    )

    assert response["result_code"] == "ACCEPTED"
    assert repository.recorded == [
        {
            "task_id": "3001",
            "pinky_id": "pinky1",
            "guide_phase": "READY_TO_START_GUIDANCE",
            "target_track_id": 17,
            "reason_code": "",
            "seq": 42,
            "occurred_at": None,
        }
    ]
    assert navigation.navigated == []


def test_processor_closes_finished_task_then_dispatches_return_to_dock_once():
    repository = FakeGuidePhaseSnapshotRepository(
        response={
            "result_code": "ACCEPTED",
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "COMPLETED",
            "phase": "GUIDANCE_FINISHED",
            "guide_phase": "GUIDANCE_FINISHED",
            "assigned_robot_id": "pinky1",
            "target_track_id": 17,
        }
    )
    navigation = FakeGoalPoseNavigationService()
    processor = GuidePhaseSnapshotProcessor(
        guide_phase_snapshot_repository=repository,
        goal_pose_navigation_service=navigation,
        return_to_dock_goal_pose_resolver=_dock_pose,
        return_to_dock_timeout_sec=90,
    )

    first = processor.process(
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "guide_phase": "GUIDANCE_FINISHED",
            "target_track_id": -1,
            "reason_code": "ARRIVED",
            "seq": 100,
        }
    )
    duplicate = processor.process(
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "guide_phase": "GUIDANCE_FINISHED",
            "target_track_id": -1,
            "reason_code": "ARRIVED",
            "seq": 100,
        }
    )

    assert first["task_status"] == "COMPLETED"
    assert first["phase"] == "GUIDANCE_FINISHED"
    assert first["return_to_dock_response"]["result_code"] == "ACCEPTED"
    assert duplicate["result_code"] == "IGNORED"
    assert duplicate["reason_code"] == "STALE_GUIDE_PHASE_SNAPSHOT"
    assert navigation.navigated == [
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "nav_phase": "RETURN_TO_DOCK",
            "goal_pose": _dock_pose(),
            "timeout_sec": 90,
        }
    ]


def test_processor_does_not_change_finished_task_outcome_when_return_to_dock_fails():
    repository = FakeGuidePhaseSnapshotRepository(
        response={
            "result_code": "ACCEPTED",
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "COMPLETED",
            "phase": "GUIDANCE_FINISHED",
            "guide_phase": "GUIDANCE_FINISHED",
            "assigned_robot_id": "pinky1",
            "target_track_id": 17,
        }
    )
    navigation = FakeGoalPoseNavigationService(
        response={"result_code": "REJECTED", "reason_code": "DOCK_BLOCKED"}
    )
    processor = GuidePhaseSnapshotProcessor(
        guide_phase_snapshot_repository=repository,
        goal_pose_navigation_service=navigation,
        return_to_dock_goal_pose_resolver=_dock_pose,
    )

    response = processor.process(
        {
            "task_id": 3001,
            "pinky_id": "pinky1",
            "guide_phase": "GUIDANCE_FINISHED",
            "target_track_id": 17,
            "seq": 7,
        }
    )

    assert response["task_status"] == "COMPLETED"
    assert response["phase"] == "GUIDANCE_FINISHED"
    assert response["return_to_dock_response"] == {
        "result_code": "REJECTED",
        "reason_code": "DOCK_BLOCKED",
    }


def test_async_processor_records_snapshot_and_dispatches_return_to_dock():
    repository = FakeGuidePhaseSnapshotRepository(
        response={
            "result_code": "ACCEPTED",
            "task_id": 3001,
            "task_type": "GUIDE",
            "task_status": "COMPLETED",
            "phase": "GUIDANCE_FINISHED",
            "guide_phase": "GUIDANCE_FINISHED",
            "assigned_robot_id": "pinky1",
            "target_track_id": 17,
        }
    )
    navigation = FakeGoalPoseNavigationService()
    processor = GuidePhaseSnapshotProcessor(
        guide_phase_snapshot_repository=repository,
        goal_pose_navigation_service=navigation,
        return_to_dock_goal_pose_resolver=_dock_pose,
    )

    response = asyncio.run(
        processor.async_process(
            {
                "task_id": 3001,
                "pinky_id": "pinky1",
                "guide_phase": "GUIDANCE_FINISHED",
                "target_track_id": 17,
                "seq": 1,
            }
        )
    )

    assert response["return_to_dock_response"]["result_code"] == "ACCEPTED"
    assert navigation.navigated[0]["nav_phase"] == "RETURN_TO_DOCK"
