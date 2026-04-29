import asyncio

from server.ropi_main_service.application.patrol_orchestrator import PatrolOrchestrator


class FakePatrolPathExecutionService:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "result_code": "SUCCESS",
            "result_message": "patrol completed",
            "completed_waypoint_count": 2,
        }

    async def async_execute(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def build_path_snapshot():
    return {
        "header": {"frame_id": "map"},
        "poses": [
            {
                "pose": {
                    "position": {"x": 1.0, "y": 2.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                }
            },
            {
                "pose": {
                    "position": {"x": 3.0, "y": 4.0, "z": 0.0},
                    "orientation": {"x": 0.0, "y": 0.0, "z": 1.0, "w": 0.0},
                }
            },
        ],
    }


def test_patrol_orchestrator_executes_patrol_path_once():
    execution_service = FakePatrolPathExecutionService()
    orchestrator = PatrolOrchestrator(
        patrol_path_execution_service=execution_service,
        patrol_timeout_sec=180,
    )

    response = asyncio.run(
        orchestrator.async_run(
            task_id=2001,
            path_snapshot_json=build_path_snapshot(),
        )
    )

    assert response["result_code"] == "SUCCESS"
    assert execution_service.calls == [
        {
            "task_id": 2001,
            "path_snapshot_json": build_path_snapshot(),
            "timeout_sec": 180,
        }
    ]


def test_patrol_orchestrator_normalizes_failure_response():
    execution_service = FakePatrolPathExecutionService(
        result={
            "result_code": "FAILED",
            "result_message": "patrol action failed",
            "reason_code": "PATROL_PATH_ACTION_FAILED",
        }
    )
    orchestrator = PatrolOrchestrator(
        patrol_path_execution_service=execution_service,
    )

    response = asyncio.run(
        orchestrator.async_run(
            task_id=2001,
            path_snapshot_json=build_path_snapshot(),
        )
    )

    assert response["result_code"] == "FAILED"
    assert response["reason_code"] == "PATROL_PATH_ACTION_FAILED"
