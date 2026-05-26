import asyncio

from server.ropi_main_service.ros.nav2_navigate_to_pose_action_client import (
    RclpyNav2NavigateToPoseActionClient,
)
from test_support.ros_action import (
    FakeActionClient,
    FakeActionResultWrapper,
    FakeGoalHandle,
)


class _Stamp:
    def __init__(self):
        self.sec = 0
        self.nanosec = 0


class _Header:
    def __init__(self):
        self.stamp = _Stamp()
        self.frame_id = ""


class _Position:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0


class _Orientation:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.w = 1.0


class _Pose:
    def __init__(self):
        self.position = _Position()
        self.orientation = _Orientation()


class _PoseStamped:
    def __init__(self):
        self.header = _Header()
        self.pose = _Pose()


class _Goal:
    def __init__(self):
        self.pose = _PoseStamped()
        self.behavior_tree = ""


class _Result:
    def __init__(self, *, error_code=0, error_msg=""):
        self.error_code = error_code
        self.error_msg = error_msg


class FakeNavigateToPose:
    Goal = _Goal


def build_goal():
    return {
        "task_id": "3001",
        "nav_phase": "DRIVE_WAYPOINT_1",
        "pose": {
            "header": {"frame_id": "map"},
            "pose": {
                "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                "orientation": {"x": 0.0, "y": 0.0, "z": 0.5, "w": 0.5},
            },
        },
        "behavior_tree": "",
        "timeout_sec": 120,
    }


def test_send_goal_serializes_only_nav2_goal_fields_and_normalizes_success():
    created_clients = []

    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        client.goal_handle = FakeGoalHandle(
            accepted=True,
            result_wrapper=FakeActionResultWrapper(
                status=4,
                result=_Result(error_code=0),
            ),
        )
        created_clients.append(client)
        return client

    client = RclpyNav2NavigateToPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToPose,
        action_client_factory=action_client_factory,
    )

    response = client.send_goal(
        action_name="/pinky1/navigate_to_pose",
        goal=build_goal(),
        result_wait_timeout_sec=125.0,
    )

    assert response["accepted"] is True
    assert response["status"] == 4
    assert response["error_code"] == 0
    assert response["result_code"] == "SUCCESS"
    assert response["result_message"] == "Nav2 NavigateToPose succeeded."

    goal_msg = created_clients[0].sent_goals[0]
    assert goal_msg.pose.header.frame_id == "map"
    assert goal_msg.pose.pose.position.x == 1.0
    assert goal_msg.pose.pose.position.y == 2.0
    assert goal_msg.pose.pose.orientation.z == 0.5
    assert goal_msg.behavior_tree == ""
    assert not hasattr(goal_msg, "task_id")
    assert not hasattr(goal_msg, "nav_phase")
    assert not hasattr(goal_msg, "timeout_sec")


def test_send_goal_normalizes_nav2_abort_result():
    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        client.goal_handle = FakeGoalHandle(
            accepted=True,
            result_wrapper=FakeActionResultWrapper(
                status=6,
                result=_Result(error_code=801, error_msg="planner failed"),
            ),
        )
        return client

    client = RclpyNav2NavigateToPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToPose,
        action_client_factory=action_client_factory,
    )

    response = client.send_goal(
        action_name="/pinky1/navigate_to_pose",
        goal=build_goal(),
        result_wait_timeout_sec=125.0,
    )

    assert response["result_code"] == "FAILED"
    assert response["reason_code"] == "NAV2_ERROR_801"
    assert response["result_message"] == "planner failed"


def test_async_send_goal_normalizes_nav2_success():
    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        client.goal_handle = FakeGoalHandle(
            accepted=True,
            result_wrapper=FakeActionResultWrapper(
                status=4,
                result=_Result(error_code=0),
            ),
        )
        return client

    client = RclpyNav2NavigateToPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToPose,
        action_client_factory=action_client_factory,
    )

    response = asyncio.run(
        client.async_send_goal(
            action_name="/pinky1/navigate_to_pose",
            goal=build_goal(),
            result_wait_timeout_sec=125.0,
        )
    )

    assert response["result_code"] == "SUCCESS"
