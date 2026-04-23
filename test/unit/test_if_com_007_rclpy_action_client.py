import pytest

from server.ropi_main_service.ros.goal_pose_action_client import RclpyGoalPoseActionClient


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
        self.w = 0.0


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
        self.task_id = ""
        self.nav_phase = ""
        self.goal_pose = _PoseStamped()
        self.timeout_sec = 0


class FakeNavigateToGoal:
    Goal = _Goal


class FakeActionClient:
    def __init__(self, node, action_type, action_name):
        self.node = node
        self.action_type = action_type
        self.action_name = action_name
        self.wait_calls = []
        self.sent_goals = []
        self.server_available = True

    def wait_for_server(self, timeout_sec=None):
        self.wait_calls.append(timeout_sec)
        return self.server_available

    def send_goal_async(self, goal_msg):
        self.sent_goals.append(goal_msg)
        return "future-token"


def build_goal():
    return {
        "task_id": "task_delivery_001",
        "nav_phase": "DELIVERY_DESTINATION",
        "goal_pose": {
            "header": {
                "stamp": {
                    "sec": 1776554120,
                    "nanosec": 0,
                },
                "frame_id": "map",
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
        },
        "timeout_sec": 120,
    }


def test_send_goal_builds_if_com_007_ros_goal_and_dispatches_to_action_client():
    created_clients = []

    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        created_clients.append(client)
        return client

    client = RclpyGoalPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToGoal,
        action_client_factory=action_client_factory,
    )

    response = client.send_goal(
        action_name="/ropi/control/pinky2/navigate_to_goal",
        goal=build_goal(),
    )

    assert response["submitted"] is True
    assert response["send_goal_future"] == "future-token"
    assert len(created_clients) == 1
    assert created_clients[0].action_name == "/ropi/control/pinky2/navigate_to_goal"
    assert created_clients[0].wait_calls == [1.0]

    goal_msg = created_clients[0].sent_goals[0]
    assert goal_msg.task_id == "task_delivery_001"
    assert goal_msg.nav_phase == "DELIVERY_DESTINATION"
    assert goal_msg.goal_pose.header.frame_id == "map"
    assert goal_msg.goal_pose.header.stamp.sec == 1776554120
    assert goal_msg.goal_pose.pose.position.x == 18.4
    assert goal_msg.goal_pose.pose.position.y == 7.2
    assert goal_msg.goal_pose.pose.orientation.z == 1.0
    assert goal_msg.timeout_sec == 120


def test_send_goal_raises_when_ros_action_server_is_unavailable():
    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        client.server_available = False
        return client

    client = RclpyGoalPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToGoal,
        action_client_factory=action_client_factory,
    )

    with pytest.raises(RuntimeError, match="not available"):
        client.send_goal(
            action_name="/ropi/control/pinky2/navigate_to_goal",
            goal=build_goal(),
        )
