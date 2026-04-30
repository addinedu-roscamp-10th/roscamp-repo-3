import asyncio

from server.ropi_main_service.ros.command_dispatcher import RosServiceCommandDispatcher


class FakeAsyncActionClient:
    def __init__(self):
        self.goal_calls = []
        self.ready_calls = []
        self.cancel_calls = []

    def send_goal(self, **kwargs):
        raise AssertionError("async dispatcher should prefer async_send_goal")

    async def async_send_goal(self, **kwargs):
        self.goal_calls.append(kwargs)
        return {
            "accepted": True,
            "status": 4,
            "result_code": "SUCCESS",
            "result_message": "navigation done",
        }

    def is_server_ready(self, **kwargs):
        raise AssertionError("async dispatcher should prefer async_is_server_ready")

    async def async_is_server_ready(self, **kwargs):
        self.ready_calls.append(kwargs)
        return True

    async def async_cancel_goal(self, **kwargs):
        self.cancel_calls.append(kwargs)
        return {
            "result_code": "CANCEL_REQUESTED",
            "cancel_requested": True,
            "matched_goal_count": 1,
        }

    def get_latest_feedback(self, **kwargs):
        return [
            {
                "task_id": kwargs["task_id"],
                "action_name": "/ropi/control/pinky2/navigate_to_goal",
                "action_type": "navigation",
                "feedback_type": "NAVIGATION_FEEDBACK",
                "received_at": "2026-04-28T00:00:00+00:00",
                "payload": {
                    "nav_status": "MOVING",
                    "distance_remaining_m": 1.25,
                },
            }
        ]


class FakeAsyncGoalPoseActionClient(FakeAsyncActionClient):
    pass


class FakeAsyncPatrolActionClient(FakeAsyncActionClient):
    async def async_send_goal(self, **kwargs):
        self.goal_calls.append(kwargs)
        return {
            "accepted": True,
            "status": 4,
            "result_code": "SUCCEEDED",
            "result_message": "patrol done",
        }


class FakeAsyncManipulationActionClient:
    def __init__(self):
        self.goal_calls = []
        self.ready_calls = []
        self.cancel_calls = []

    def send_goal(self, **kwargs):
        raise AssertionError("async dispatcher should prefer async_send_goal")

    async def async_send_goal(self, **kwargs):
        self.goal_calls.append(kwargs)
        return {
            "accepted": True,
            "status": 4,
            "result_code": "SUCCESS",
            "result_message": "manipulation done",
            "processed_quantity": 2,
        }

    def is_server_ready(self, **kwargs):
        raise AssertionError("async dispatcher should prefer async_is_server_ready")

    async def async_is_server_ready(self, **kwargs):
        self.ready_calls.append(kwargs)
        return True

    async def async_cancel_goal(self, **kwargs):
        self.cancel_calls.append(kwargs)
        return {
            "result_code": "NOT_FOUND",
            "cancel_requested": False,
            "matched_goal_count": 0,
        }

    def get_latest_feedback(self, **kwargs):
        return []


class FakeAsyncFallResponseControlClient:
    def __init__(self):
        self.calls = []

    def call(self, **kwargs):
        raise AssertionError("async dispatcher should prefer async_call")

    async def async_call(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "accepted": True,
            "message": "",
        }


def test_async_dispatch_prefers_async_goal_pose_action_client():
    goal_client = FakeAsyncGoalPoseActionClient()
    dispatcher = RosServiceCommandDispatcher(goal_pose_action_client=goal_client)

    async def scenario():
        try:
            return await dispatcher.async_dispatch(
                "navigate_to_goal",
                {
                    "pinky_id": "pinky2",
                    "goal": {
                        "task_id": "task_delivery_001",
                        "nav_phase": "DELIVERY_DESTINATION",
                        "timeout_sec": 120,
                    },
                },
            )
        finally:
            dispatcher.close()

    response = asyncio.run(scenario())

    assert response["result_code"] == "SUCCESS"
    assert goal_client.goal_calls == [
        {
            "action_name": "/ropi/control/pinky2/navigate_to_goal",
            "goal": {
                "task_id": "task_delivery_001",
                "nav_phase": "DELIVERY_DESTINATION",
                "timeout_sec": 120,
            },
            "result_wait_timeout_sec": 125.0,
        }
    ]


def test_async_dispatch_prefers_async_manipulation_action_client():
    manipulation_client = FakeAsyncManipulationActionClient()
    dispatcher = RosServiceCommandDispatcher(
        goal_pose_action_client=FakeAsyncGoalPoseActionClient(),
        manipulation_action_client=manipulation_client,
    )

    async def scenario():
        try:
            return await dispatcher.async_dispatch(
                "execute_manipulation",
                {
                    "arm_id": "arm1",
                    "goal": {
                        "task_id": "task_delivery_001",
                        "transfer_direction": "TO_ROBOT",
                        "item_id": "med_acetaminophen_500",
                        "quantity": 2,
                        "robot_slot_id": "robot_slot_a1",
                    },
                },
            )
        finally:
            dispatcher.close()

    response = asyncio.run(scenario())

    assert response["result_code"] == "SUCCESS"
    assert manipulation_client.goal_calls[0]["action_name"] == "/ropi/arm/arm1/execute_manipulation"
    assert manipulation_client.goal_calls[0]["result_wait_timeout_sec"] == 30.0


def test_async_dispatch_execute_patrol_path_uses_patrol_action_client():
    patrol_client = FakeAsyncPatrolActionClient()
    dispatcher = RosServiceCommandDispatcher(
        goal_pose_action_client=FakeAsyncGoalPoseActionClient(),
        patrol_path_action_client=patrol_client,
    )
    path = {
        "header": {"frame_id": "map"},
        "poses": [
            {
                "pose": {
                    "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                }
            }
        ],
    }

    async def scenario():
        try:
            return await dispatcher.async_dispatch(
                "execute_patrol_path",
                {
                    "pinky_id": "pinky3",
                    "goal": {
                        "task_id": "2001",
                        "path": path,
                        "timeout_sec": 180,
                    },
                },
            )
        finally:
            dispatcher.close()

    response = asyncio.run(scenario())

    assert response["result_code"] == "SUCCEEDED"
    assert patrol_client.goal_calls == [
        {
            "action_name": "/ropi/control/pinky3/execute_patrol_path",
            "goal": {
                "task_id": "2001",
                "path": path,
                "timeout_sec": 180,
            },
            "result_wait_timeout_sec": 185.0,
        }
    ]


def test_async_dispatch_fall_response_control_uses_service_client():
    fall_response_client = FakeAsyncFallResponseControlClient()
    dispatcher = RosServiceCommandDispatcher(
        goal_pose_action_client=FakeAsyncGoalPoseActionClient(),
        fall_response_control_client=fall_response_client,
    )

    async def scenario():
        try:
            return await dispatcher.async_dispatch(
                "fall_response_control",
            {
                "pinky_id": "pinky3",
                "request": {
                    "task_id": "2001",
                    "command_type": "CLEAR_AND_RESTART",
                    },
                },
            )
        finally:
            dispatcher.close()

    response = asyncio.run(scenario())

    assert response == {
        "accepted": True,
        "message": "",
    }
    assert fall_response_client.calls == [
        {
            "service_name": "/ropi/control/pinky3/fall_response_control",
            "request": {
                "task_id": "2001",
                "command_type": "CLEAR_AND_RESTART",
            },
        }
    ]


def test_async_dispatch_fall_response_control_accepts_flat_patrol_payload():
    fall_response_client = FakeAsyncFallResponseControlClient()
    dispatcher = RosServiceCommandDispatcher(
        goal_pose_action_client=FakeAsyncGoalPoseActionClient(),
        fall_response_control_client=fall_response_client,
    )

    async def scenario():
        try:
            return await dispatcher.async_dispatch(
                "fall_response_control",
                {
                    "task_id": "2001",
                    "command_type": "CLEAR_AND_STOP",
                },
            )
        finally:
            dispatcher.close()

    response = asyncio.run(scenario())

    assert response == {
        "accepted": True,
        "message": "",
    }
    assert fall_response_client.calls == [
        {
            "service_name": "/ropi/control/pinky3/fall_response_control",
            "request": {
                "task_id": "2001",
                "command_type": "CLEAR_AND_STOP",
            },
        }
    ]


def test_async_dispatch_runtime_status_prefers_async_readiness_checks():
    goal_client = FakeAsyncGoalPoseActionClient()
    manipulation_client = FakeAsyncManipulationActionClient()
    dispatcher = RosServiceCommandDispatcher(
        goal_pose_action_client=goal_client,
        manipulation_action_client=manipulation_client,
    )

    async def scenario():
        try:
            return await dispatcher.async_dispatch(
                "get_runtime_status",
                {
                    "pinky_id": "pinky2",
                    "arm_ids": ["arm1"],
                },
            )
        finally:
            dispatcher.close()

    response = asyncio.run(scenario())

    assert response["ready"] is True
    assert goal_client.ready_calls == [
        {
            "action_name": "/ropi/control/pinky2/navigate_to_goal",
            "wait_timeout_sec": 0.0,
        }
    ]
    assert manipulation_client.ready_calls == [
        {
            "action_name": "/ropi/arm/arm1/execute_manipulation",
            "wait_timeout_sec": 0.0,
        }
    ]


def test_async_dispatch_runtime_status_checks_patrol_only_when_requested():
    goal_client = FakeAsyncGoalPoseActionClient()
    patrol_client = FakeAsyncActionClient()
    dispatcher = RosServiceCommandDispatcher(
        goal_pose_action_client=goal_client,
        patrol_path_action_client=patrol_client,
    )

    async def scenario():
        try:
            first = await dispatcher.async_dispatch(
                "get_runtime_status",
                {
                    "pinky_id": "pinky2",
                    "arm_ids": [],
                },
            )
            second = await dispatcher.async_dispatch(
                "get_runtime_status",
                {
                    "pinky_id": "pinky2",
                    "include_patrol": True,
                    "patrol_pinky_id": "pinky3",
                    "arm_ids": [],
                },
            )
            return first, second
        finally:
            dispatcher.close()

    first, second = asyncio.run(scenario())

    assert first["checks"] == [
        {
            "name": "pinky2.navigate_to_goal",
            "ready": True,
            "action_name": "/ropi/control/pinky2/navigate_to_goal",
        }
    ]
    assert patrol_client.ready_calls == [
        {
            "action_name": "/ropi/control/pinky3/execute_patrol_path",
            "wait_timeout_sec": 0.0,
        }
    ]
    assert second["checks"][1] == {
        "name": "pinky3.execute_patrol_path",
        "ready": True,
        "action_name": "/ropi/control/pinky3/execute_patrol_path",
    }


def test_async_dispatch_cancel_action_cancels_matching_goal_by_task_id():
    goal_client = FakeAsyncGoalPoseActionClient()
    manipulation_client = FakeAsyncManipulationActionClient()
    dispatcher = RosServiceCommandDispatcher(
        goal_pose_action_client=goal_client,
        manipulation_action_client=manipulation_client,
    )

    async def scenario():
        try:
            return await dispatcher.async_dispatch(
                "cancel_action",
                {
                    "task_id": "task_delivery_001",
                },
            )
        finally:
            dispatcher.close()

    response = asyncio.run(scenario())

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert response["cancel_requested"] is True
    assert goal_client.cancel_calls == [
        {
            "task_id": "task_delivery_001",
            "action_name": None,
        }
    ]
    assert manipulation_client.cancel_calls == [
        {
            "task_id": "task_delivery_001",
            "action_name": None,
        }
    ]


def test_async_dispatch_get_action_feedback_returns_latest_feedback_by_task_id():
    goal_client = FakeAsyncGoalPoseActionClient()
    manipulation_client = FakeAsyncManipulationActionClient()
    dispatcher = RosServiceCommandDispatcher(
        goal_pose_action_client=goal_client,
        manipulation_action_client=manipulation_client,
    )

    async def scenario():
        try:
            return await dispatcher.async_dispatch(
                "get_action_feedback",
                {
                    "task_id": "task_delivery_001",
                },
            )
        finally:
            dispatcher.close()

    response = asyncio.run(scenario())

    assert response == {
        "result_code": "FOUND",
        "task_id": "task_delivery_001",
        "action_name": None,
        "feedback": [
            {
                "client": "navigation",
                "task_id": "task_delivery_001",
                "action_name": "/ropi/control/pinky2/navigate_to_goal",
                "action_type": "navigation",
                "feedback_type": "NAVIGATION_FEEDBACK",
                "received_at": "2026-04-28T00:00:00+00:00",
                "payload": {
                    "nav_status": "MOVING",
                    "distance_remaining_m": 1.25,
                },
            }
        ],
    }
