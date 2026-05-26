import asyncio

from server.ropi_main_service.application.drive_runtime import (
    DriveOrchestrator,
    build_drive_request_service,
)


class FakeTaskRequestRepository:
    def __init__(self):
        self.calls = []

    async def async_create_drive_task(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "result_code": "ACCEPTED",
            "task_id": 3001,
            "task_type": "DRIVE",
            "task_status": "WAITING_DISPATCH",
            "phase": "REQUESTED",
            "assigned_robot_id": kwargs["robot_id"],
            "map_id": "map_0504",
            "route_id": kwargs["route_id"],
        }


class FakeDriveExecutionRepository:
    def __init__(self, *, events, snapshot):
        self.events = events
        self.snapshot = snapshot
        self.waiting_records = []
        self.started = []
        self.results = []

    async def async_get_drive_execution_snapshot(self, task_id):
        self.events.append("snapshot")
        return dict(self.snapshot, task_id=int(task_id))

    async def async_record_drive_reservation_waiting(
        self,
        *,
        task_id,
        reservation_response,
    ):
        self.events.append("waiting")
        self.waiting_records.append(
            {
                "task_id": task_id,
                "reservation_response": reservation_response,
            }
        )
        return {
            "result_code": "ACCEPTED",
            "task_id": int(task_id),
            "task_status": "WAITING_DISPATCH",
            "phase": "WAITING_FMS_RESERVATION",
        }

    async def async_record_drive_execution_started(self, task_id):
        self.events.append("started")
        self.started.append(task_id)
        return {
            "result_code": "ACCEPTED",
            "task_id": int(task_id),
            "task_status": "RUNNING",
            "phase": "FOLLOW_DRIVE_ROUTE",
        }

    async def async_record_drive_task_workflow_result(
        self,
        *,
        task_id,
        workflow_response,
    ):
        self.events.append("result")
        self.results.append(
            {
                "task_id": task_id,
                "workflow_response": workflow_response,
            }
        )
        return {
            "result_code": workflow_response.get("result_code"),
            "task_id": int(task_id),
        }


class FakeFmsRuntime:
    def __init__(self, *, events, result_code="HELD"):
        self.events = events
        self.result_codes = (
            list(result_code)
            if isinstance(result_code, list)
            else [result_code]
        )
        self.requested = []
        self.released = []

    def request_reservation(self, **kwargs):
        self.events.append("reserve")
        self.requested.append(kwargs)
        result_code = (
            self.result_codes.pop(0)
            if len(self.result_codes) > 1
            else self.result_codes[0]
        )
        reason_code = None
        if result_code == "WAITING":
            reason_code = "FMS_RESOURCE_ALREADY_HELD"
        return {
            "result_code": result_code,
            "reservation_status": result_code,
            "reason_code": reason_code,
            "next_task_phase": (
                "WAITING_FMS_RESERVATION"
                if result_code == "WAITING"
                else None
            ),
            "reservations": [],
        }

    def release_reservation(self, **kwargs):
        self.events.append("release")
        self.released.append(kwargs)
        return {"result_code": "RELEASED", "released_count": 1}


class FakeDriveOrchestrator:
    def __init__(self, *, events, response=None):
        self.events = events
        self.response = response or {
            "result_code": "SUCCESS",
            "result_message": "drive route completed.",
            "reason_code": None,
        }
        self.calls = []

    async def async_run(self, **kwargs):
        self.events.append("navigate")
        self.calls.append(kwargs)
        return dict(self.response)


class FakeWorkflowTaskManager:
    def __init__(self):
        self.tasks = []

    def create_task(
        self,
        coro,
        *,
        name=None,
        loop=None,
        cancel_on_shutdown=True,
    ):
        task = (loop or asyncio.get_running_loop()).create_task(coro, name=name)
        self.tasks.append(task)
        return task


class FakeNavigationService:
    def __init__(self):
        self.calls = []

    async def async_navigate(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "result_code": "SUCCESS",
            "result_message": "goal reached.",
            "reason_code": None,
        }


def _drive_payload():
    return {
        "request_id": "req_drive_001",
        "caregiver_id": "1",
        "robot_id": "pinky1",
        "route_id": "route_corridor",
        "priority": "NORMAL",
        "notes": None,
        "idempotency_key": "idem_drive_001",
    }


def _snapshot():
    return {
        "task_id": 3001,
        "assigned_robot_id": "pinky1",
        "map_id": "map_0504",
        "path_snapshot_json": {
            "header": {"frame_id": "map"},
            "poses": [
                {
                    "sequence_no": 1,
                    "waypoint_id": "corridor_01",
                    "x": 0.0,
                    "y": 0.0,
                    "yaw": 0.0,
                },
                {
                    "sequence_no": 2,
                    "waypoint_id": "corridor_02",
                    "x": 1.0,
                    "y": 0.0,
                    "yaw": 1.57,
                },
            ],
        },
        "reservation_resources": [
            {"resource_type": "WAYPOINT", "resource_id": "corridor_01"},
            {"resource_type": "EDGE", "resource_id": "edge_corridor_01_02"},
            {"resource_type": "WAYPOINT", "resource_id": "corridor_02"},
        ],
    }


def test_drive_runtime_reserves_before_navigation_and_releases_after_success():
    async def _run():
        events = []
        manager = FakeWorkflowTaskManager()
        task_repository = FakeTaskRequestRepository()
        execution_repository = FakeDriveExecutionRepository(
            events=events,
            snapshot=_snapshot(),
        )
        fms_runtime = FakeFmsRuntime(events=events)
        drive_orchestrator = FakeDriveOrchestrator(events=events)
        service = build_drive_request_service(
            loop=asyncio.get_running_loop(),
            workflow_task_manager=manager,
            task_request_repository=task_repository,
            drive_execution_repository=execution_repository,
            fms_runtime_service=fms_runtime,
            drive_orchestrator=drive_orchestrator,
        )

        response = await service.async_create_drive_task(**_drive_payload())
        await asyncio.gather(*manager.tasks)

        assert response["result_code"] == "ACCEPTED"
        assert events == ["snapshot", "reserve", "started", "navigate", "release", "result"]
        assert fms_runtime.requested == [
            {
                "task_id": 3001,
                "robot_id": "pinky1",
                "map_id": "map_0504",
                "resources": _snapshot()["reservation_resources"],
                "lease_sec": 30,
            }
        ]
        assert drive_orchestrator.calls[0]["robot_id"] == "pinky1"
        assert drive_orchestrator.calls[0]["path_snapshot_json"] == _snapshot()[
            "path_snapshot_json"
        ]
        assert fms_runtime.released == [
            {"task_id": 3001, "robot_id": "pinky1", "reason_code": "COMPLETED"}
        ]
        assert execution_repository.results[0]["workflow_response"]["result_code"] == "SUCCESS"

    asyncio.run(_run())


def test_drive_runtime_records_waiting_without_navigation_when_reservation_conflicts():
    async def _run():
        events = []
        manager = FakeWorkflowTaskManager()
        execution_repository = FakeDriveExecutionRepository(
            events=events,
            snapshot=_snapshot(),
        )
        fms_runtime = FakeFmsRuntime(events=events, result_code="WAITING")
        drive_orchestrator = FakeDriveOrchestrator(events=events)
        service = build_drive_request_service(
            loop=asyncio.get_running_loop(),
            workflow_task_manager=manager,
            task_request_repository=FakeTaskRequestRepository(),
            drive_execution_repository=execution_repository,
            fms_runtime_service=fms_runtime,
            drive_orchestrator=drive_orchestrator,
            fms_reservation_retry_max_attempts=1,
        )

        await service.async_create_drive_task(**_drive_payload())
        await asyncio.gather(*manager.tasks)

        assert events == ["snapshot", "reserve", "waiting"]
        assert drive_orchestrator.calls == []
        assert fms_runtime.released == []
        assert execution_repository.waiting_records[0]["reservation_response"][
            "reason_code"
        ] == "FMS_RESOURCE_ALREADY_HELD"
        assert execution_repository.results == []

    asyncio.run(_run())


def test_drive_runtime_retries_waiting_reservation_and_dispatches_when_held():
    async def _run():
        events = []
        manager = FakeWorkflowTaskManager()
        execution_repository = FakeDriveExecutionRepository(
            events=events,
            snapshot=_snapshot(),
        )
        fms_runtime = FakeFmsRuntime(events=events, result_code=["WAITING", "HELD"])
        drive_orchestrator = FakeDriveOrchestrator(events=events)
        service = build_drive_request_service(
            loop=asyncio.get_running_loop(),
            workflow_task_manager=manager,
            task_request_repository=FakeTaskRequestRepository(),
            drive_execution_repository=execution_repository,
            fms_runtime_service=fms_runtime,
            drive_orchestrator=drive_orchestrator,
            fms_reservation_retry_interval_sec=0,
        )

        await service.async_create_drive_task(**_drive_payload())
        await asyncio.gather(*manager.tasks)

        assert events == [
            "snapshot",
            "reserve",
            "waiting",
            "reserve",
            "started",
            "navigate",
            "release",
            "result",
        ]
        assert len(fms_runtime.requested) == 2
        assert len(execution_repository.waiting_records) == 1
        assert drive_orchestrator.calls[0]["robot_id"] == "pinky1"
        assert execution_repository.results[0]["workflow_response"]["result_code"] == "SUCCESS"

    asyncio.run(_run())


def test_drive_orchestrator_sends_namespaced_goal_for_each_route_waypoint():
    async def _run():
        navigation = FakeNavigationService()
        orchestrator = DriveOrchestrator(
            goal_pose_navigation_service=navigation,
            drive_navigation_timeout_sec=42,
        )

        response = await orchestrator.async_run(
            task_id=3001,
            robot_id="pinky3",
            path_snapshot_json=_snapshot()["path_snapshot_json"],
        )

        assert response["result_code"] == "SUCCESS"
        assert [call["pinky_id"] for call in navigation.calls] == ["pinky3", "pinky3"]
        assert [call["nav_phase"] for call in navigation.calls] == [
            "DRIVE_WAYPOINT_1",
            "DRIVE_WAYPOINT_2",
        ]
        assert navigation.calls[1]["goal_pose"]["header"]["frame_id"] == "map"
        assert navigation.calls[1]["goal_pose"]["pose"]["position"]["x"] == 1.0

    asyncio.run(_run())
