import asyncio

import pytest

from server.ropi_main_service.ros.goal_pose_action_client import RclpyGoalPoseActionClient
from test_support.ros_action import (
    FakeActionClient,
    FakeActionResultWrapper,
    FakeGoalHandle,
)


class _Stamp:
    def __init__(self, sec=0, nanosec=0):
        self.sec = sec
        self.nanosec = nanosec


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


class _Result:
    def __init__(self):
        self.result_code = ""
        self.result_message = ""
        self.final_pose = _PoseStamped()
        self.finished_at = _Stamp()


class FakeNavigateToGoal:
    Goal = _Goal


class NeverCompletingFuture:
    def add_done_callback(self, callback):
        pass


class ControlledFuture:
    def __init__(self):
        self._callbacks = []
        self._result = None
        self._done = False

    def add_done_callback(self, callback):
        if self._done:
            callback(self)
            return

        self._callbacks.append(callback)

    def set_result(self, result):
        self._result = result
        self._done = True
        callbacks = list(self._callbacks)
        self._callbacks.clear()
        for callback in callbacks:
            callback(self)

    def result(self):
        return self._result


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


def build_result(*, result_code="SUCCESS", result_message="navigation done"):
    result = _Result()
    result.result_code = result_code
    result.result_message = result_message
    result.final_pose.header.frame_id = "map"
    result.final_pose.pose.position.x = 18.4
    result.final_pose.pose.position.y = 7.2
    result.finished_at.sec = 1776554240
    return result


def test_send_goal_waits_for_final_if_com_007_result_and_serializes_payload():
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

    client = RclpyGoalPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToGoal,
        action_client_factory=action_client_factory,
    )

    response = client.send_goal(
        action_name="/ropi/control/pinky2/navigate_to_goal",
        goal=build_goal(),
        result_wait_timeout_sec=125.0,
    )

    assert response["accepted"] is True
    assert response["status"] == 4
    assert response["result_code"] == "SUCCESS"
    assert response["result_message"] == "navigation done"
    assert response["final_pose"]["header"]["frame_id"] == "map"
    assert response["final_pose"]["pose"]["position"]["x"] == 18.4
    assert response["finished_at"]["sec"] == 1776554240
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


def test_async_send_goal_waits_for_final_if_com_007_result_and_serializes_payload():
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

    client = RclpyGoalPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToGoal,
        action_client_factory=action_client_factory,
    )

    response = asyncio.run(
        client.async_send_goal(
            action_name="/ropi/control/pinky2/navigate_to_goal",
            goal=build_goal(),
            result_wait_timeout_sec=125.0,
        )
    )

    assert response["accepted"] is True
    assert response["status"] == 4
    assert response["result_code"] == "SUCCESS"
    assert response["final_pose"]["pose"]["position"]["x"] == 18.4
    assert len(created_clients) == 1
    assert created_clients[0].wait_calls == [1.0]

    goal_msg = created_clients[0].sent_goals[0]
    assert goal_msg.task_id == "task_delivery_001"
    assert goal_msg.nav_phase == "DELIVERY_DESTINATION"
    assert goal_msg.goal_pose.header.frame_id == "map"


def test_send_goal_returns_rejected_when_ros_action_goal_is_rejected():
    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        client.goal_handle = FakeGoalHandle(accepted=False)
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

    assert response == {
        "accepted": False,
        "result_code": "REJECTED",
        "result_message": "/ropi/control/pinky2/navigate_to_goal goal was rejected.",
    }


def test_async_send_goal_returns_rejected_when_ros_action_goal_is_rejected():
    def action_client_factory(node, action_type, action_name):
        client = FakeActionClient(node, action_type, action_name)
        client.goal_handle = FakeGoalHandle(accepted=False)
        return client

    client = RclpyGoalPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToGoal,
        action_client_factory=action_client_factory,
    )

    response = asyncio.run(
        client.async_send_goal(
            action_name="/ropi/control/pinky2/navigate_to_goal",
            goal=build_goal(),
        )
    )

    assert response == {
        "accepted": False,
        "result_code": "REJECTED",
        "result_message": "/ropi/control/pinky2/navigate_to_goal goal was rejected.",
    }


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


def test_async_send_goal_raises_when_ros_action_server_is_unavailable():
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
        asyncio.run(
            client.async_send_goal(
                action_name="/ropi/control/pinky2/navigate_to_goal",
                goal=build_goal(),
            )
        )


def test_async_send_goal_raises_when_goal_response_times_out():
    class SlowActionClient(FakeActionClient):
        def send_goal_async(self, goal_msg):
            self.sent_goals.append(goal_msg)
            return NeverCompletingFuture()

    def action_client_factory(node, action_type, action_name):
        return SlowActionClient(node, action_type, action_name)

    client = RclpyGoalPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToGoal,
        action_client_factory=action_client_factory,
        goal_response_wait_timeout_sec=0.01,
    )

    with pytest.raises(RuntimeError, match="goal response timed out"):
        asyncio.run(
            client.async_send_goal(
                action_name="/ropi/control/pinky2/navigate_to_goal",
                goal=build_goal(),
            )
        )


def test_async_cancel_goal_cancels_active_goal_by_task_id():
    result_future = ControlledFuture()
    goal_handle = FakeGoalHandle(
        accepted=True,
        result_wrapper=FakeActionResultWrapper(
            status=4,
            result=build_result(),
        ),
    )

    class WaitingActionClient(FakeActionClient):
        def send_goal_async(self, goal_msg):
            self.sent_goals.append(goal_msg)
            goal_handle.get_result_async = lambda: result_future
            return super().send_goal_async(goal_msg)

    def action_client_factory(node, action_type, action_name):
        client = WaitingActionClient(node, action_type, action_name)
        client.goal_handle = goal_handle
        return client

    client = RclpyGoalPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToGoal,
        action_client_factory=action_client_factory,
    )

    async def scenario():
        send_task = asyncio.create_task(
            client.async_send_goal(
                action_name="/ropi/control/pinky2/navigate_to_goal",
                goal=build_goal(),
                result_wait_timeout_sec=1.0,
            )
        )
        for _ in range(20):
            if client._find_active_goal_matches(
                task_id="task_delivery_001",
                action_name="/ropi/control/pinky2/navigate_to_goal",
            ):
                break
            await asyncio.sleep(0.01)

        cancel_response = await client.async_cancel_goal(
            task_id="task_delivery_001",
            action_name="/ropi/control/pinky2/navigate_to_goal",
        )
        result_future.set_result(
            FakeActionResultWrapper(
                status=4,
                result=build_result(),
            )
        )
        await send_task
        return cancel_response

    response = asyncio.run(scenario())

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert response["cancel_requested"] is True
    assert response["matched_goal_count"] == 1
    assert goal_handle.cancel_calls == 1


def test_async_send_goal_cancels_ros_goal_when_coroutine_is_cancelled():
    result_future = ControlledFuture()
    goal_handle = FakeGoalHandle(
        accepted=True,
        result_wrapper=FakeActionResultWrapper(
            status=4,
            result=build_result(),
        ),
    )

    class WaitingActionClient(FakeActionClient):
        def send_goal_async(self, goal_msg):
            self.sent_goals.append(goal_msg)
            goal_handle.get_result_async = lambda: result_future
            return super().send_goal_async(goal_msg)

    def action_client_factory(node, action_type, action_name):
        client = WaitingActionClient(node, action_type, action_name)
        client.goal_handle = goal_handle
        return client

    client = RclpyGoalPoseActionClient(
        node="fake-node",
        action_type_loader=lambda: FakeNavigateToGoal,
        action_client_factory=action_client_factory,
    )

    async def scenario():
        send_task = asyncio.create_task(
            client.async_send_goal(
                action_name="/ropi/control/pinky2/navigate_to_goal",
                goal=build_goal(),
                result_wait_timeout_sec=1.0,
            )
        )
        for _ in range(20):
            if client._find_active_goal_matches(
                task_id="task_delivery_001",
                action_name="/ropi/control/pinky2/navigate_to_goal",
            ):
                break
            await asyncio.sleep(0.01)
        send_task.cancel()

        try:
            await send_task
        except asyncio.CancelledError:
            return

        raise AssertionError("async_send_goal should propagate cancellation")

    asyncio.run(scenario())

    assert goal_handle.cancel_calls == 1


def test_async_is_server_ready_uses_wait_timeout():
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

    ready = asyncio.run(
        client.async_is_server_ready(
            action_name="/ropi/control/pinky2/navigate_to_goal",
            wait_timeout_sec=0.25,
        )
    )

    assert ready is True
    assert created_clients[0].wait_calls == [0.25]
