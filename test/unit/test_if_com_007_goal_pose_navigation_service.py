import pytest

from server.ropi_main_service.services.goal_pose_navigation_service import (
    GoalPoseNavigationService,
)


class FakeGoalPoseActionClient:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "accepted": True,
            "goal_handle_id": "goal_handle_001",
        }

    def send_goal(self, *, action_name, goal):
        self.calls.append(
            {
                "action_name": action_name,
                "goal": goal,
            }
        )
        return self.result


def build_goal_pose(*, frame_id="map"):
    return {
        "header": {
            "stamp": {
                "sec": 1776554120,
                "nanosec": 0,
            },
            "frame_id": frame_id,
        },
        "pose": {
            "position": {
                "x": 18.4,
                "y": 7.2,
                "z": 0.0,
            },
            "orientation": {
                "x": 0.0,
                "y": 0.0,
                "z": 1.0,
                "w": 0.0,
            },
        },
    }


def test_navigate_delivery_destination_uses_fixed_pinky2_action_name():
    action_client = FakeGoalPoseActionClient()
    service = GoalPoseNavigationService(action_client=action_client)

    response = service.navigate(
        task_id="task_delivery_001",
        nav_phase="DELIVERY_DESTINATION",
        goal_pose=build_goal_pose(),
        timeout_sec=120,
    )

    assert action_client.calls == [
        {
            "action_name": "/ropi/control/pinky2/navigate_to_goal",
            "goal": {
                "task_id": "task_delivery_001",
                "nav_phase": "DELIVERY_DESTINATION",
                "goal_pose": build_goal_pose(),
                "timeout_sec": 120,
            },
        }
    ]
    assert response["accepted"] is True
    assert response["goal_handle_id"] == "goal_handle_001"


def test_navigate_defaults_goal_pose_frame_id_to_map():
    action_client = FakeGoalPoseActionClient()
    service = GoalPoseNavigationService(action_client=action_client)

    service.navigate(
        task_id="task_delivery_002",
        nav_phase="DELIVERY_PICKUP",
        goal_pose=build_goal_pose(frame_id=""),
        timeout_sec=90,
    )

    forwarded_goal_pose = action_client.calls[0]["goal"]["goal_pose"]
    assert forwarded_goal_pose["header"]["frame_id"] == "map"


def test_navigate_rejects_non_delivery_phase_in_phase1():
    action_client = FakeGoalPoseActionClient()
    service = GoalPoseNavigationService(action_client=action_client)

    with pytest.raises(ValueError, match="nav_phase"):
        service.navigate(
            task_id="task_delivery_003",
            nav_phase="GUIDE_DESTINATION",
            goal_pose=build_goal_pose(),
            timeout_sec=60,
        )

    assert action_client.calls == []
