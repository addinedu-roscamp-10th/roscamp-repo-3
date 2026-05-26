import asyncio

from server.ropi_main_service.ros.command_dispatcher import (
    RosServiceCommandDispatcher,
)


class FakeGoalPoseActionClient:
    pass


class FakeInitialPosePublisher:
    def __init__(self):
        self.calls = []

    def publish_initial_pose(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "result_code": "ACCEPTED",
            "robot_id": kwargs["robot_id"],
            "topic": f"/{kwargs['robot_id']}/initialpose",
            "frame_id": kwargs["frame_id"],
            "x": kwargs["x"],
            "y": kwargs["y"],
            "yaw": kwargs["yaw"],
        }


def test_dispatcher_routes_set_initial_pose_to_publisher():
    initial_pose_publisher = FakeInitialPosePublisher()
    dispatcher = RosServiceCommandDispatcher(
        goal_pose_action_client=FakeGoalPoseActionClient(),
        initial_pose_publisher=initial_pose_publisher,
    )

    try:
        response = dispatcher.dispatch(
            "set_initial_pose",
            {
                "robot_id": "pinky1",
                "frame_id": "map",
                "x": 1.25,
                "y": -0.5,
                "yaw": 1.57,
                "covariance": None,
            },
        )
    finally:
        dispatcher.close()

    assert response["result_code"] == "ACCEPTED"
    assert initial_pose_publisher.calls == [
        {
            "robot_id": "pinky1",
            "frame_id": "map",
            "x": 1.25,
            "y": -0.5,
            "yaw": 1.57,
            "covariance": None,
        }
    ]


def test_async_dispatcher_routes_set_initial_pose_to_publisher():
    initial_pose_publisher = FakeInitialPosePublisher()
    dispatcher = RosServiceCommandDispatcher(
        goal_pose_action_client=FakeGoalPoseActionClient(),
        initial_pose_publisher=initial_pose_publisher,
    )

    async def scenario():
        try:
            return await dispatcher.async_dispatch(
                "set_initial_pose",
                {
                    "robot_id": "pinky3",
                    "frame_id": "map",
                    "x": 0.0,
                    "y": 0.2,
                    "yaw": 0.3,
                    "covariance": None,
                },
            )
        finally:
            dispatcher.close()

    response = asyncio.run(scenario())

    assert response["topic"] == "/pinky3/initialpose"
    assert initial_pose_publisher.calls == [
        {
            "robot_id": "pinky3",
            "frame_id": "map",
            "x": 0.0,
            "y": 0.2,
            "yaw": 0.3,
            "covariance": None,
        }
    ]
