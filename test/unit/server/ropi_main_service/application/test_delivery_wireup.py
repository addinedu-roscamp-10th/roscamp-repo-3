import asyncio
from unittest.mock import patch

from server.ropi_main_service.application import delivery_runtime
from server.ropi_main_service.application.delivery_workflow_task_manager import (
    DeliveryWorkflowTaskManager,
)
from server.ropi_main_service.application.task_request import DeliveryRequestService


class FakeDeliveryRequestRepository:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create_delivery_task(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.response)

    async def async_create_delivery_task(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.response)


class FakeDeliveryWorkflowStarter:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)


def build_request_payload():
    return {
        "request_id": "req_001",
        "caregiver_id": "1",
        "item_id": "1",
        "quantity": 2,
        "destination_id": "delivery_room_301",
        "priority": "NORMAL",
        "notes": "Medication after meals",
        "idempotency_key": "idem_delivery_001",
    }


def test_create_delivery_task_starts_delivery_workflow_after_acceptance():
    repository = FakeDeliveryRequestRepository(
        response={
            "result_code": "ACCEPTED",
            "result_message": None,
            "reason_code": None,
            "task_id": 101,
            "task_status": "WAITING_DISPATCH",
            "assigned_robot_id": "pinky2",
        }
    )
    workflow_starter = FakeDeliveryWorkflowStarter()
    service = DeliveryRequestService(
        repository=repository,
        delivery_workflow_starter=workflow_starter,
    )

    response = service.create_delivery_task(**build_request_payload())

    assert response["result_code"] == "ACCEPTED"
    assert workflow_starter.calls == [
        {
            "task_id": "101",
            "item_id": "1",
            "quantity": 2,
            "destination_id": "delivery_room_301",
        }
    ]


def test_async_create_delivery_task_starts_delivery_workflow_after_acceptance():
    repository = FakeDeliveryRequestRepository(
        response={
            "result_code": "ACCEPTED",
            "result_message": None,
            "reason_code": None,
            "task_id": 101,
            "task_status": "WAITING_DISPATCH",
            "assigned_robot_id": "pinky2",
        }
    )
    workflow_starter = FakeDeliveryWorkflowStarter()
    service = DeliveryRequestService(
        repository=repository,
        delivery_workflow_starter=workflow_starter,
    )

    response = asyncio.run(service.async_create_delivery_task(**build_request_payload()))

    assert response["result_code"] == "ACCEPTED"
    assert workflow_starter.calls == [
        {
            "task_id": "101",
            "item_id": "1",
            "quantity": 2,
            "destination_id": "delivery_room_301",
        }
    ]


def test_async_create_delivery_task_awaits_async_precheck_without_thread_offload():
    precheck_calls = []
    repository = FakeDeliveryRequestRepository(
        response={
            "result_code": "ACCEPTED",
            "result_message": None,
            "reason_code": None,
            "task_id": 101,
            "task_status": "WAITING_DISPATCH",
            "assigned_robot_id": "pinky2",
        }
    )

    async def async_precheck(**kwargs):
        precheck_calls.append(kwargs)
        return None

    service = DeliveryRequestService(
        repository=repository,
        async_delivery_request_precheck=async_precheck,
    )

    async def scenario():
        with patch(
            "server.ropi_main_service.application.task_request.asyncio.to_thread",
            side_effect=AssertionError("async precheck should not use thread fallback"),
        ):
            return await service.async_create_delivery_task(**build_request_payload())

    response = asyncio.run(scenario())

    assert response["result_code"] == "ACCEPTED"
    assert precheck_calls[0]["destination_id"] == "delivery_room_301"


def test_build_delivery_request_service_async_precheck_uses_async_ros_readiness():
    class FakeReadinessService:
        def __init__(self, **kwargs):
            pass

        def get_status(self):
            raise AssertionError("async delivery precheck should not use sync ROS readiness")

        async def async_get_status(self):
            return {"ready": True, "checks": []}

    async def scenario():
        loop = asyncio.get_running_loop()
        with patch(
            "server.ropi_main_service.application.delivery_runtime.get_delivery_navigation_config",
            return_value={
                "pickup_goal_pose": {"pose": {"position": {"x": 1.0, "y": 2.0, "z": 0.0}}},
                "destination_goal_poses": {
                    "delivery_room_301": {"pose": {"position": {"x": 3.0, "y": 4.0, "z": 0.0}}},
                },
                "return_to_dock_goal_pose": {"pose": {"position": {"x": 5.0, "y": 6.0, "z": 0.0}}},
            },
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.RosRuntimeReadinessService",
            FakeReadinessService,
        ), patch(
            "server.ropi_main_service.application.task_request.asyncio.to_thread",
            side_effect=AssertionError("async delivery precheck should not use thread fallback"),
        ):
            service = delivery_runtime.build_delivery_request_service(loop=loop)
            return await service._async_run_delivery_request_precheck(**build_request_payload())

    response = asyncio.run(scenario())

    assert response is None


def test_build_delivery_request_service_starts_async_orchestrator_without_thread_offload():
    calls = []

    class FakeDeliveryOrchestrator:
        def __init__(self, **kwargs):
            pass

        def run(self, **kwargs):
            raise AssertionError("delivery workflow should not use sync orchestrator.run")

        async def async_run(self, **kwargs):
            calls.append(kwargs)
            return {"result_code": "SUCCESS"}

    async def scenario():
        loop = asyncio.get_running_loop()
        with patch(
            "server.ropi_main_service.application.delivery_runtime.get_delivery_navigation_config",
            return_value={
                "pickup_goal_pose": {"pose": {"position": {"x": 1.0, "y": 2.0, "z": 0.0}}},
                "destination_goal_poses": {
                    "delivery_room_301": {"pose": {"position": {"x": 3.0, "y": 4.0, "z": 0.0}}},
                },
                "return_to_dock_goal_pose": {"pose": {"position": {"x": 5.0, "y": 6.0, "z": 0.0}}},
            },
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.DeliveryOrchestrator",
            FakeDeliveryOrchestrator,
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.asyncio.to_thread",
            side_effect=AssertionError("delivery workflow should not be started via to_thread"),
        ):
            service = delivery_runtime.build_delivery_request_service(loop=loop)
            service._start_delivery_workflow_if_needed(
                response={
                    "result_code": "ACCEPTED",
                    "task_id": 101,
                },
                item_id="1",
                quantity=2,
                destination_id="delivery_room_301",
            )
            await asyncio.sleep(0)

    asyncio.run(scenario())

    assert calls == [
        {
            "task_id": "101",
            "item_id": "1",
            "quantity": 2,
            "destination_id": "delivery_room_301",
        }
    ]


def test_build_delivery_request_service_records_cancelled_workflow_result():
    repository_calls = []

    class FakeDeliveryRequestRepository:
        async def async_record_delivery_task_cancelled_result(self, **kwargs):
            repository_calls.append(kwargs)
            return {"result_code": "CANCELLED"}

    class FakeDeliveryOrchestrator:
        def __init__(self, **kwargs):
            pass

        async def async_run(self, **kwargs):
            return {
                "result_code": "FAILED",
                "result_message": "goal canceled by user request.",
                "status": 5,
            }

    async def scenario():
        loop = asyncio.get_running_loop()
        with patch(
            "server.ropi_main_service.application.delivery_runtime.get_delivery_navigation_config",
            return_value={
                "pickup_goal_pose": {"pose": {"position": {"x": 1.0, "y": 2.0, "z": 0.0}}},
                "destination_goal_poses": {
                    "delivery_room_301": {"pose": {"position": {"x": 3.0, "y": 4.0, "z": 0.0}}},
                },
                "return_to_dock_goal_pose": {"pose": {"position": {"x": 5.0, "y": 6.0, "z": 0.0}}},
            },
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.DeliveryRequestRepository",
            FakeDeliveryRequestRepository,
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.DeliveryOrchestrator",
            FakeDeliveryOrchestrator,
        ):
            service = delivery_runtime.build_delivery_request_service(loop=loop)
            service._start_delivery_workflow_if_needed(
                response={
                    "result_code": "ACCEPTED",
                    "task_id": 101,
                },
                item_id="1",
                quantity=2,
                destination_id="delivery_room_301",
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

    asyncio.run(scenario())

    assert repository_calls == [
        {
            "task_id": "101",
            "workflow_response": {
                "result_code": "FAILED",
                "result_message": "goal canceled by user request.",
                "status": 5,
            },
        }
    ]


def test_build_delivery_request_service_records_successful_workflow_result():
    repository_calls = []

    class FakeDeliveryRequestRepository:
        async def async_record_delivery_task_workflow_result(self, **kwargs):
            repository_calls.append(kwargs)
            return {"result_code": "SUCCESS", "task_status": "COMPLETED"}

    class FakeDeliveryOrchestrator:
        def __init__(self, **kwargs):
            pass

        async def async_run(self, **kwargs):
            return {
                "result_code": "SUCCESS",
                "result_message": "return to dock complete.",
            }

    async def scenario():
        loop = asyncio.get_running_loop()
        with patch(
            "server.ropi_main_service.application.delivery_runtime.get_delivery_navigation_config",
            return_value={
                "pickup_goal_pose": {"pose": {"position": {"x": 1.0, "y": 2.0, "z": 0.0}}},
                "destination_goal_poses": {
                    "delivery_room_301": {"pose": {"position": {"x": 3.0, "y": 4.0, "z": 0.0}}},
                },
                "return_to_dock_goal_pose": {"pose": {"position": {"x": 5.0, "y": 6.0, "z": 0.0}}},
            },
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.DeliveryRequestRepository",
            FakeDeliveryRequestRepository,
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.DeliveryOrchestrator",
            FakeDeliveryOrchestrator,
        ):
            service = delivery_runtime.build_delivery_request_service(loop=loop)
            service._start_delivery_workflow_if_needed(
                response={
                    "result_code": "ACCEPTED",
                    "task_id": 101,
                },
                item_id="1",
                quantity=2,
                destination_id="delivery_room_301",
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

    asyncio.run(scenario())

    assert repository_calls == [
        {
            "task_id": "101",
            "workflow_response": {
                "result_code": "SUCCESS",
                "result_message": "return to dock complete.",
            },
        }
    ]


def test_build_delivery_request_service_records_failed_workflow_result_when_orchestrator_raises():
    repository_calls = []

    class FakeDeliveryRequestRepository:
        async def async_record_delivery_task_workflow_result(self, **kwargs):
            repository_calls.append(kwargs)
            return {"result_code": "FAILED", "task_status": "FAILED"}

    class FakeDeliveryOrchestrator:
        def __init__(self, **kwargs):
            pass

        async def async_run(self, **kwargs):
            raise RuntimeError("navigation action crashed")

    async def scenario():
        loop = asyncio.get_running_loop()
        with patch(
            "server.ropi_main_service.application.delivery_runtime.get_delivery_navigation_config",
            return_value={
                "pickup_goal_pose": {"pose": {"position": {"x": 1.0, "y": 2.0, "z": 0.0}}},
                "destination_goal_poses": {
                    "delivery_room_301": {"pose": {"position": {"x": 3.0, "y": 4.0, "z": 0.0}}},
                },
                "return_to_dock_goal_pose": {"pose": {"position": {"x": 5.0, "y": 6.0, "z": 0.0}}},
            },
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.DeliveryRequestRepository",
            FakeDeliveryRequestRepository,
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.DeliveryOrchestrator",
            FakeDeliveryOrchestrator,
        ):
            service = delivery_runtime.build_delivery_request_service(loop=loop)
            service._start_delivery_workflow_if_needed(
                response={
                    "result_code": "ACCEPTED",
                    "task_id": 101,
                },
                item_id="1",
                quantity=2,
                destination_id="delivery_room_301",
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

    asyncio.run(scenario())

    assert repository_calls == [
        {
            "task_id": "101",
            "workflow_response": {
                "result_code": "FAILED",
                "result_message": "delivery workflow background task failed: navigation action crashed",
                "reason_code": "WORKFLOW_UNHANDLED_EXCEPTION",
            },
        }
    ]


def test_build_delivery_request_service_records_failed_result_when_workflow_task_is_cancelled():
    repository_calls = []

    class FakeDeliveryRequestRepository:
        async def async_record_delivery_task_workflow_result(self, **kwargs):
            repository_calls.append(kwargs)
            return {"result_code": "FAILED", "task_status": "FAILED"}

    class FakeDeliveryOrchestrator:
        def __init__(self, **kwargs):
            pass

        async def async_run(self, **kwargs):
            await asyncio.sleep(3600)

    async def scenario():
        loop = asyncio.get_running_loop()
        workflow_task_manager = DeliveryWorkflowTaskManager()
        with patch(
            "server.ropi_main_service.application.delivery_runtime.get_delivery_navigation_config",
            return_value={
                "pickup_goal_pose": {"pose": {"position": {"x": 1.0, "y": 2.0, "z": 0.0}}},
                "destination_goal_poses": {
                    "delivery_room_301": {"pose": {"position": {"x": 3.0, "y": 4.0, "z": 0.0}}},
                },
                "return_to_dock_goal_pose": {"pose": {"position": {"x": 5.0, "y": 6.0, "z": 0.0}}},
            },
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.DeliveryRequestRepository",
            FakeDeliveryRequestRepository,
        ), patch(
            "server.ropi_main_service.application.delivery_runtime.DeliveryOrchestrator",
            FakeDeliveryOrchestrator,
        ):
            service = delivery_runtime.build_delivery_request_service(
                loop=loop,
                workflow_task_manager=workflow_task_manager,
            )
            service._start_delivery_workflow_if_needed(
                response={
                    "result_code": "ACCEPTED",
                    "task_id": 101,
                },
                item_id="1",
                quantity=2,
                destination_id="delivery_room_301",
            )
            await asyncio.sleep(0)
            await workflow_task_manager.shutdown(timeout_sec=1)

    asyncio.run(scenario())

    assert repository_calls == [
        {
            "task_id": "101",
            "workflow_response": {
                "result_code": "FAILED",
                "result_message": "delivery workflow background task was cancelled.",
                "reason_code": "WORKFLOW_TASK_CANCELLED",
            },
        }
    ]


def test_create_delivery_task_does_not_start_delivery_workflow_when_request_is_rejected():
    repository = FakeDeliveryRequestRepository(
        response={
            "result_code": "REJECTED",
            "result_message": "요청한 item_id를 현재 물품 목록에서 찾을 수 없습니다.",
            "reason_code": "ITEM_NOT_FOUND",
            "task_id": None,
            "task_status": None,
            "assigned_robot_id": None,
        }
    )
    workflow_starter = FakeDeliveryWorkflowStarter()
    service = DeliveryRequestService(
        repository=repository,
        delivery_workflow_starter=workflow_starter,
    )

    response = service.create_delivery_task(**build_request_payload())

    assert response["result_code"] == "REJECTED"
    assert workflow_starter.calls == []
