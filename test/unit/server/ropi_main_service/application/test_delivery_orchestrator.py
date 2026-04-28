import logging

import pytest

from server.ropi_main_service.application.delivery_orchestrator import DeliveryOrchestrator


class FakeGoalPoseNavigationService:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def navigate(self, **kwargs):
        self.calls.append(kwargs)
        return self.results.pop(0)


class FakeManipulationCommandService:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return self.results.pop(0)


class FakePickupGoalPoseResolver:
    def __init__(self, goal_pose):
        self.goal_pose = goal_pose
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.goal_pose


class FakeDestinationGoalPoseResolver:
    def __init__(self, goal_pose):
        self.goal_pose = goal_pose
        self.calls = []

    def __call__(self, destination_id):
        self.calls.append(destination_id)
        return self.goal_pose


class FakeReturnToDockGoalPoseResolver:
    def __init__(self, goal_pose):
        self.goal_pose = goal_pose
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.goal_pose


def build_goal_pose(x=1.5, y=2.5):
    return {
        "header": {
            "stamp": {"sec": 0, "nanosec": 0},
            "frame_id": "map",
        },
        "pose": {
            "position": {"x": x, "y": y, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        },
    }


def build_success_response(result_message=None):
    return {
        "result_code": "SUCCESS",
        "result_message": result_message,
    }


def test_run_delivery_workflow_executes_pickup_load_destination_unload_in_order():
    navigation_service = FakeGoalPoseNavigationService(
        [
            build_success_response(),
            build_success_response(),
            build_success_response(),
        ]
    )
    manipulation_service = FakeManipulationCommandService(
        [
            build_success_response(),
            build_success_response(),
        ]
    )
    pickup_resolver = FakePickupGoalPoseResolver(build_goal_pose(x=1.5, y=2.5))
    destination_resolver = FakeDestinationGoalPoseResolver(build_goal_pose(x=18.4, y=7.2))
    return_to_dock_resolver = FakeReturnToDockGoalPoseResolver(build_goal_pose(x=0.5, y=0.5))
    orchestrator = DeliveryOrchestrator(
        goal_pose_navigation_service=navigation_service,
        manipulation_command_service=manipulation_service,
        pickup_goal_pose_resolver=pickup_resolver,
        destination_goal_pose_resolver=destination_resolver,
        return_to_dock_goal_pose_resolver=return_to_dock_resolver,
    )

    response = orchestrator.run(
        task_id="task_delivery_001",
        item_id="1",
        quantity=2,
        destination_id="room2",
    )

    assert response["result_code"] == "SUCCESS"
    assert pickup_resolver.calls == 1
    assert destination_resolver.calls == ["room2"]
    assert return_to_dock_resolver.calls == 1
    assert navigation_service.calls == [
        {
            "task_id": "task_delivery_001",
            "nav_phase": "DELIVERY_PICKUP",
            "goal_pose": build_goal_pose(x=1.5, y=2.5),
            "timeout_sec": 120,
        },
        {
            "task_id": "task_delivery_001",
            "nav_phase": "DELIVERY_DESTINATION",
            "goal_pose": build_goal_pose(x=18.4, y=7.2),
            "timeout_sec": 120,
        },
        {
            "task_id": "task_delivery_001",
            "nav_phase": "RETURN_TO_DOCK",
            "goal_pose": build_goal_pose(x=0.5, y=0.5),
            "timeout_sec": 120,
        },
    ]
    assert manipulation_service.calls == [
        {
            "arm_id": "arm1",
            "task_id": "task_delivery_001",
            "transfer_direction": "TO_ROBOT",
            "item_id": "1",
            "quantity": 2,
        },
        {
            "arm_id": "arm2",
            "task_id": "task_delivery_001",
            "transfer_direction": "FROM_ROBOT",
            "item_id": "1",
            "quantity": 2,
        },
    ]


def test_run_delivery_workflow_stops_after_pickup_navigation_failure():
    navigation_service = FakeGoalPoseNavigationService(
        [
            {
                "result_code": "FAILED",
                "result_message": "pickup navigation failed",
            }
        ]
    )
    manipulation_service = FakeManipulationCommandService([])
    orchestrator = DeliveryOrchestrator(
        goal_pose_navigation_service=navigation_service,
        manipulation_command_service=manipulation_service,
        pickup_goal_pose_resolver=FakePickupGoalPoseResolver(build_goal_pose()),
        destination_goal_pose_resolver=FakeDestinationGoalPoseResolver(build_goal_pose(x=18.4, y=7.2)),
        return_to_dock_goal_pose_resolver=FakeReturnToDockGoalPoseResolver(build_goal_pose(x=0.5, y=0.5)),
    )

    response = orchestrator.run(
        task_id="task_delivery_001",
        item_id="1",
        quantity=2,
        destination_id="room2",
    )

    assert response == {
        "result_code": "FAILED",
        "result_message": "pickup navigation failed",
    }
    assert len(navigation_service.calls) == 1
    assert manipulation_service.calls == []


def test_run_delivery_workflow_stops_when_destination_goal_pose_is_missing():
    navigation_service = FakeGoalPoseNavigationService(
        [build_success_response()]
    )
    manipulation_service = FakeManipulationCommandService(
        [build_success_response()]
    )
    destination_resolver = FakeDestinationGoalPoseResolver(None)
    orchestrator = DeliveryOrchestrator(
        goal_pose_navigation_service=navigation_service,
        manipulation_command_service=manipulation_service,
        pickup_goal_pose_resolver=FakePickupGoalPoseResolver(build_goal_pose()),
        destination_goal_pose_resolver=destination_resolver,
        return_to_dock_goal_pose_resolver=FakeReturnToDockGoalPoseResolver(build_goal_pose(x=0.5, y=0.5)),
    )

    response = orchestrator.run(
        task_id="task_delivery_001",
        item_id="1",
        quantity=2,
        destination_id="room2",
    )

    assert response == {
        "result_code": "FAILED",
        "result_message": "destination goal pose를 찾을 수 없습니다.",
        "reason_code": "DESTINATION_GOAL_POSE_MISSING",
    }
    assert destination_resolver.calls == ["room2"]
    assert len(navigation_service.calls) == 1
    assert len(manipulation_service.calls) == 1


def test_run_delivery_workflow_stops_when_return_to_dock_goal_pose_is_missing():
    navigation_service = FakeGoalPoseNavigationService(
        [
            build_success_response(),
            build_success_response(),
        ]
    )
    manipulation_service = FakeManipulationCommandService(
        [
            build_success_response(),
            build_success_response(),
        ]
    )
    return_to_dock_resolver = FakeReturnToDockGoalPoseResolver(None)
    orchestrator = DeliveryOrchestrator(
        goal_pose_navigation_service=navigation_service,
        manipulation_command_service=manipulation_service,
        pickup_goal_pose_resolver=FakePickupGoalPoseResolver(build_goal_pose()),
        destination_goal_pose_resolver=FakeDestinationGoalPoseResolver(build_goal_pose(x=18.4, y=7.2)),
        return_to_dock_goal_pose_resolver=return_to_dock_resolver,
    )

    response = orchestrator.run(
        task_id="task_delivery_001",
        item_id="1",
        quantity=2,
        destination_id="room2",
    )

    assert response == {
        "result_code": "FAILED",
        "result_message": "return_to_dock goal pose를 찾을 수 없습니다.",
        "reason_code": "RETURN_TO_DOCK_GOAL_POSE_MISSING",
    }
    assert return_to_dock_resolver.calls == 1
    assert len(navigation_service.calls) == 2
    assert len(manipulation_service.calls) == 2


def test_run_delivery_workflow_stops_after_load_failure():
    navigation_service = FakeGoalPoseNavigationService(
        [build_success_response()]
    )
    manipulation_service = FakeManipulationCommandService(
        [
            {
                "result_code": "FAILED",
                "result_message": "load failed",
            }
        ]
    )
    orchestrator = DeliveryOrchestrator(
        goal_pose_navigation_service=navigation_service,
        manipulation_command_service=manipulation_service,
        pickup_goal_pose_resolver=FakePickupGoalPoseResolver(build_goal_pose()),
        destination_goal_pose_resolver=FakeDestinationGoalPoseResolver(build_goal_pose(x=18.4, y=7.2)),
        return_to_dock_goal_pose_resolver=FakeReturnToDockGoalPoseResolver(build_goal_pose(x=0.5, y=0.5)),
    )

    response = orchestrator.run(
        task_id="task_delivery_001",
        item_id="1",
        quantity=2,
        destination_id="room2",
    )

    assert response == {
        "result_code": "FAILED",
        "result_message": "load failed",
    }
    assert len(navigation_service.calls) == 1
    assert len(manipulation_service.calls) == 1


def test_run_delivery_workflow_stops_after_destination_navigation_failure():
    navigation_service = FakeGoalPoseNavigationService(
        [
            build_success_response(),
            {
                "result_code": "FAILED",
                "result_message": "destination navigation failed",
            },
        ]
    )
    manipulation_service = FakeManipulationCommandService(
        [build_success_response()]
    )
    orchestrator = DeliveryOrchestrator(
        goal_pose_navigation_service=navigation_service,
        manipulation_command_service=manipulation_service,
        pickup_goal_pose_resolver=FakePickupGoalPoseResolver(build_goal_pose()),
        destination_goal_pose_resolver=FakeDestinationGoalPoseResolver(build_goal_pose(x=18.4, y=7.2)),
        return_to_dock_goal_pose_resolver=FakeReturnToDockGoalPoseResolver(build_goal_pose(x=0.5, y=0.5)),
    )

    response = orchestrator.run(
        task_id="task_delivery_001",
        item_id="1",
        quantity=2,
        destination_id="room2",
    )

    assert response == {
        "result_code": "FAILED",
        "result_message": "destination navigation failed",
    }
    assert len(navigation_service.calls) == 2
    assert len(manipulation_service.calls) == 1


def test_run_delivery_workflow_stops_after_unload_failure():
    navigation_service = FakeGoalPoseNavigationService(
        [
            build_success_response(),
            build_success_response(),
        ]
    )
    manipulation_service = FakeManipulationCommandService(
        [
            build_success_response(),
            {
                "result_code": "FAILED",
                "result_message": "unload failed",
            },
        ]
    )
    return_to_dock_resolver = FakeReturnToDockGoalPoseResolver(build_goal_pose(x=0.5, y=0.5))
    orchestrator = DeliveryOrchestrator(
        goal_pose_navigation_service=navigation_service,
        manipulation_command_service=manipulation_service,
        pickup_goal_pose_resolver=FakePickupGoalPoseResolver(build_goal_pose()),
        destination_goal_pose_resolver=FakeDestinationGoalPoseResolver(build_goal_pose(x=18.4, y=7.2)),
        return_to_dock_goal_pose_resolver=return_to_dock_resolver,
    )

    response = orchestrator.run(
        task_id="task_delivery_001",
        item_id="1",
        quantity=2,
        destination_id="room2",
    )

    assert response == {
        "result_code": "FAILED",
        "result_message": "unload failed",
    }
    assert return_to_dock_resolver.calls == 0
    assert len(navigation_service.calls) == 2
    assert len(manipulation_service.calls) == 2


def test_run_delivery_workflow_logs_failure_stage(caplog):
    navigation_service = FakeGoalPoseNavigationService(
        [
            build_success_response(),
            {
                "result_code": "FAILED",
                "result_message": "destination navigation failed",
            },
        ]
    )
    manipulation_service = FakeManipulationCommandService(
        [build_success_response()]
    )
    orchestrator = DeliveryOrchestrator(
        goal_pose_navigation_service=navigation_service,
        manipulation_command_service=manipulation_service,
        pickup_goal_pose_resolver=FakePickupGoalPoseResolver(build_goal_pose()),
        destination_goal_pose_resolver=FakeDestinationGoalPoseResolver(build_goal_pose(x=18.4, y=7.2)),
        return_to_dock_goal_pose_resolver=FakeReturnToDockGoalPoseResolver(build_goal_pose(x=0.5, y=0.5)),
    )

    with caplog.at_level(logging.INFO):
        response = orchestrator.run(
            task_id="task_delivery_001",
            item_id="1",
            quantity=2,
            destination_id="room2",
        )

    assert response["result_code"] == "FAILED"
    assert "delivery_workflow_started" in caplog.text
    assert "delivery_destination_navigation_failed" in caplog.text
