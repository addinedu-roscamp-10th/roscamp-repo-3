import pytest

from server.ropi_main_service.ros.manipulation_action_client import RclpyManipulationActionClient


class _Goal:
    def __init__(self):
        self.task_id = ""
        self.transfer_direction = ""
        self.item_id = ""
        self.quantity = 0
        self.robot_slot_id = ""


class FakeExecuteManipulation:
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
        "transfer_direction": "TO_ROBOT",
        "item_id": "med_acetaminophen_500",
        "quantity": 2,
        "robot_slot_id": "robot_slot_a1",
    }


def test_send_goal_builds_if_del_003_ros_goal_and_dispatches_to_action_client():
    created_clients = []

    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        created_clients.append(client)
        return client

    client = RclpyManipulationActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeExecuteManipulation,
        action_client_factory=action_client_factory,
    )

    response = client.send_goal(
        action_name="/ropi/arm/arm1/execute_manipulation",
        goal=build_goal(),
    )

    assert response["submitted"] is True
    assert response["send_goal_future"] == "future-token"
    assert len(created_clients) == 1
    assert created_clients[0].action_name == "/ropi/arm/arm1/execute_manipulation"
    assert created_clients[0].wait_calls == [1.0]

    goal_msg = created_clients[0].sent_goals[0]
    assert goal_msg.task_id == "task_delivery_001"
    assert goal_msg.transfer_direction == "TO_ROBOT"
    assert goal_msg.item_id == "med_acetaminophen_500"
    assert goal_msg.quantity == 2
    assert goal_msg.robot_slot_id == "robot_slot_a1"


def test_send_goal_raises_when_manipulation_action_server_is_unavailable():
    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        client.server_available = False
        return client

    client = RclpyManipulationActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeExecuteManipulation,
        action_client_factory=action_client_factory,
    )

    with pytest.raises(RuntimeError, match="not available"):
        client.send_goal(
            action_name="/ropi/arm/arm1/execute_manipulation",
            goal=build_goal(),
        )
