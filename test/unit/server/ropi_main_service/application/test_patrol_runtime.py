import asyncio

from server.ropi_main_service.application.delivery_workflow_task_manager import (
    DeliveryWorkflowTaskManager,
)
from server.ropi_main_service.application import patrol_runtime


class FakeRepository:
    async def async_get_patrol_execution_snapshot(self, task_id):
        return {
            "task_id": int(task_id),
            "assigned_robot_id": "pinky3",
            "path_snapshot_json": {
                "header": {"frame_id": "map"},
                "poses": [
                    {
                        "pose": {
                            "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                            "orientation": {
                                "x": 0.0,
                                "y": 0.0,
                                "z": 0.0,
                                "w": 1.0,
                            },
                        }
                    }
                ],
            },
        }


class FakeOrchestrator:
    def __init__(self):
        self.calls = []

    async def async_run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "result_code": "SUCCESS",
            "result_message": "patrol completed",
        }


def test_build_patrol_request_service_starts_background_patrol_workflow():
    workflow_task_manager = DeliveryWorkflowTaskManager()
    repository = FakeRepository()
    orchestrator = FakeOrchestrator()

    async def scenario():
        service = patrol_runtime.build_patrol_request_service(
            loop=asyncio.get_running_loop(),
            workflow_task_manager=workflow_task_manager,
            patrol_execution_repository=repository,
            patrol_orchestrator=orchestrator,
        )
        service.patrol_workflow_starter(task_id="2001")
        await workflow_task_manager.join(timeout_sec=1.0)

    asyncio.run(scenario())

    assert orchestrator.calls == [
        {
            "task_id": "2001",
            "path_snapshot_json": {
                "header": {"frame_id": "map"},
                "poses": [
                    {
                        "pose": {
                            "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                            "orientation": {
                                "x": 0.0,
                                "y": 0.0,
                                "z": 0.0,
                                "w": 1.0,
                            },
                        }
                    }
                ],
            },
        }
    ]
