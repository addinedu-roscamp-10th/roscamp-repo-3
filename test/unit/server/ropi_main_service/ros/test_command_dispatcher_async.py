import asyncio

from server.ropi_main_service.ros.command_dispatcher import RosServiceCommandDispatcher


class FakeAsyncGoalPoseActionClient:
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
