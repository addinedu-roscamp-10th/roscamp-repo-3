import pytest

from server.ropi_main_service.ros.manipulation_action_client import RclpyManipulationActionClient


class _Goal:
    def __init__(self):
        self.task_id = ""
        self.transfer_direction = ""
        self.item_id = ""
        self.quantity = 0
        self.robot_slot_id = ""


class _Result:
    def __init__(self):
        self.result_code = ""
        self.result_message = ""
        self.processed_quantity = 0


class FakeArmManipulation:
    Goal = _Goal


class FakeFuture:
    def __init__(self, result=None, exception=None):
        self._result = result
        self._exception = exception

    def add_done_callback(self, callback):
        callback(self)

    def result(self):
        if self._exception is not None:
            raise self._exception
        return self._result


class FakeGoalHandle:
    def __init__(self, *, accepted, result_wrapper=None):
        self.accepted = accepted
        self._result_wrapper = result_wrapper

    def get_result_async(self):
        return FakeFuture(result=self._result_wrapper)


class FakeActionResultWrapper:
    def __init__(self, *, status, result):
        self.status = status
        self.result = result


class FakeActionClient:
    def __init__(self, node, action_type, action_name):
        self.node = node
        self.action_type = action_type
        self.action_name = action_name
        self.wait_calls = []
        self.sent_goals = []
        self.server_available = True
        self.goal_handle = None

    def wait_for_server(self, timeout_sec=None):
        self.wait_calls.append(timeout_sec)
        return self.server_available

    def send_goal_async(self, goal_msg):
        self.sent_goals.append(goal_msg)
        return FakeFuture(result=self.goal_handle)


def build_goal():
    return {
        "task_id": "task_delivery_001",
        "transfer_direction": "TO_ROBOT",
        "item_id": "med_acetaminophen_500",
        "quantity": 2,
        "robot_slot_id": "robot_slot_a1",
    }


def build_result():
    result = _Result()
    result.result_code = "SUCCESS"
    result.result_message = "manipulation done"
    result.processed_quantity = 2
    return result


def test_send_goal_waits_for_final_if_del_003_result_and_serializes_payload():
    created_clients = []

    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        client.goal_handle = FakeGoalHandle(
            accepted=True,
            result_wrapper=FakeActionResultWrapper(
                status=4,
                result=build_result(),
            ),
        )
        created_clients.append(client)
        return client

    client = RclpyManipulationActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeArmManipulation,
        action_client_factory=action_client_factory,
    )

    response = client.send_goal(
        action_name="/ropi/arm/arm1/execute_manipulation",
        goal=build_goal(),
        result_wait_timeout_sec=30.0,
    )

    assert response == {
        "accepted": True,
        "status": 4,
        "result_code": "SUCCESS",
        "result_message": "manipulation done",
        "processed_quantity": 2,
    }
    assert len(created_clients) == 1
    assert created_clients[0].action_name == "/ropi/arm/arm1/execute_manipulation"
    assert created_clients[0].wait_calls == [1.0]

    goal_msg = created_clients[0].sent_goals[0]
    assert goal_msg.task_id == "task_delivery_001"
    assert goal_msg.transfer_direction == "TO_ROBOT"
    assert goal_msg.item_id == "med_acetaminophen_500"
    assert goal_msg.quantity == 2
    assert goal_msg.robot_slot_id == "robot_slot_a1"


def test_send_goal_returns_rejected_when_manipulation_goal_is_rejected():
    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        client.goal_handle = FakeGoalHandle(accepted=False)
        return client

    client = RclpyManipulationActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeArmManipulation,
        action_client_factory=action_client_factory,
    )

    response = client.send_goal(
        action_name="/ropi/arm/arm1/execute_manipulation",
        goal=build_goal(),
    )

    assert response == {
        "accepted": False,
        "result_code": "REJECTED",
        "result_message": "/ropi/arm/arm1/execute_manipulation goal was rejected.",
    }


def test_send_goal_raises_when_manipulation_action_server_is_unavailable():
    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        client.server_available = False
        return client

    client = RclpyManipulationActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeArmManipulation,
        action_client_factory=action_client_factory,
    )

    with pytest.raises(RuntimeError, match="not available"):
        client.send_goal(
            action_name="/ropi/arm/arm1/execute_manipulation",
            goal=build_goal(),
        )
