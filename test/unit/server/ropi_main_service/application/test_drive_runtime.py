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
        self.snapshots = list(snapshot) if isinstance(snapshot, list) else None
        self.waiting_records = []
        self.started = []
        self.results = []

    async def async_get_drive_execution_snapshot(self, task_id):
        self.events.append("snapshot")
        if self.snapshots is not None:
            snapshot = self.snapshots.pop(0) if len(self.snapshots) > 1 else self.snapshots[0]
            return dict(snapshot, task_id=int(task_id))
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
    def __init__(self, *, events, result_code="HELD", renew_event=None):
        self.events = events
        self.result_codes = (
            list(result_code)
            if isinstance(result_code, list)
            else [result_code]
        )
        self.renew_event = renew_event
        self.requested = []
        self.renewed = []
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

    def renew_reservation(self, **kwargs):
        self.events.append("renew")
        self.renewed.append(kwargs)
        if self.renew_event is not None:
            self.renew_event.set()
        return {"result_code": "RENEWED", "renewed_count": 3}


class FakeDriveOrchestrator:
    def __init__(self, *, events, response=None, wait_for_event=None):
        self.events = events
        self.response = response or {
            "result_code": "SUCCESS",
            "result_message": "drive route completed.",
            "reason_code": None,
        }
        self.wait_for_event = wait_for_event
        self.calls = []

    async def async_run(self, **kwargs):
        self.calls.append(kwargs)
        before_waypoint = kwargs.get("before_waypoint")
        after_waypoint = kwargs.get("after_waypoint")
        for sequence_no in (1, 2):
            if before_waypoint is not None:
                before_response = await before_waypoint(
                    sequence_no=sequence_no,
                    waypoint_index=sequence_no,
                    pose_stamped={"sequence_no": sequence_no},
                )
                if before_response is not None:
                    return before_response
            self.events.append(f"navigate_{sequence_no}")
            if self.wait_for_event is not None:
                await asyncio.wait_for(self.wait_for_event.wait(), timeout=1)
            if after_waypoint is not None:
                await after_waypoint(
                    sequence_no=sequence_no,
                    waypoint_index=sequence_no,
                    pose_stamped={"sequence_no": sequence_no},
                )
        self.events.append("navigate")
        if self.wait_for_event is not None:
            await asyncio.wait_for(self.wait_for_event.wait(), timeout=1)
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
            {"resource_type": "CONFLICT_ZONE", "resource_id": "cz_corridor_cross"},
            {"resource_type": "WAYPOINT", "resource_id": "corridor_02"},
        ],
        "reservation_segments": [
            {
                "sequence_no": 1,
                "resources": [
                    {"resource_type": "WAYPOINT", "resource_id": "corridor_01"},
                ],
            },
            {
                "sequence_no": 2,
                "resources": [
                    {"resource_type": "EDGE", "resource_id": "edge_corridor_01_02"},
                    {
                        "resource_type": "CONFLICT_ZONE",
                        "resource_id": "cz_corridor_cross",
                    },
                    {"resource_type": "WAYPOINT", "resource_id": "corridor_02"},
                ],
            },
        ],
    }


def test_drive_runtime_reserves_each_segment_before_navigation_and_releases_on_arrival():
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
        assert events == [
            "snapshot",
            "reserve",
            "started",
            "navigate_1",
            "reserve",
            "started",
            "navigate_2",
            "release",
            "navigate",
            "release",
            "result",
        ]
        assert fms_runtime.requested == [
            {
                "task_id": 3001,
                "robot_id": "pinky1",
                "map_id": "map_0504",
                "resources": _snapshot()["reservation_segments"][0]["resources"],
                "lease_sec": 30,
            },
            {
                "task_id": 3001,
                "robot_id": "pinky1",
                "map_id": "map_0504",
                "resources": _snapshot()["reservation_segments"][1]["resources"],
                "lease_sec": 30,
            }
        ]
        assert drive_orchestrator.calls[0]["robot_id"] == "pinky1"
        assert drive_orchestrator.calls[0]["path_snapshot_json"] == _snapshot()[
            "path_snapshot_json"
        ]
        assert fms_runtime.released[:2] == [
            {
                "task_id": 3001,
                "robot_id": "pinky1",
                "reason_code": "SEGMENT_COMPLETED",
                "resources": [
                    {"resource_type": "WAYPOINT", "resource_id": "corridor_01"},
                    {"resource_type": "EDGE", "resource_id": "edge_corridor_01_02"},
                    {
                        "resource_type": "CONFLICT_ZONE",
                        "resource_id": "cz_corridor_cross",
                    },
                ],
            },
            {
                "task_id": 3001,
                "robot_id": "pinky1",
                "reason_code": "COMPLETED",
                "resources": None,
            },
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
        fms_runtime = FakeFmsRuntime(
            events=events,
            result_code=["WAITING", "HELD", "HELD"],
        )
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
            "snapshot",
            "reserve",
            "started",
            "navigate_1",
            "reserve",
            "started",
            "navigate_2",
            "release",
            "navigate",
            "release",
            "result",
        ]
        assert len(fms_runtime.requested) == 3
        assert len(execution_repository.waiting_records) == 1
        assert drive_orchestrator.calls[0]["robot_id"] == "pinky1"
        assert execution_repository.results[0]["workflow_response"]["result_code"] == "SUCCESS"

    asyncio.run(_run())


def test_drive_runtime_waits_at_previous_waypoint_when_next_segment_is_blocked():
    async def _run():
        events = []
        manager = FakeWorkflowTaskManager()
        execution_repository = FakeDriveExecutionRepository(
            events=events,
            snapshot=_snapshot(),
        )
        fms_runtime = FakeFmsRuntime(
            events=events,
            result_code=["HELD", "WAITING", "HELD"],
        )
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
            "started",
            "navigate_1",
            "reserve",
            "waiting",
            "snapshot",
            "reserve",
            "started",
            "navigate_2",
            "release",
            "navigate",
            "release",
            "result",
        ]
        assert fms_runtime.requested[0]["resources"] == _snapshot()[
            "reservation_segments"
        ][0]["resources"]
        assert fms_runtime.requested[1]["resources"] == _snapshot()[
            "reservation_segments"
        ][1]["resources"]
        assert fms_runtime.requested[2]["resources"] == _snapshot()[
            "reservation_segments"
        ][1]["resources"]
        assert events.index("waiting") < events.index("navigate_2")

    asyncio.run(_run())


def test_drive_runtime_renews_fms_reservation_during_navigation():
    async def _run():
        events = []
        manager = FakeWorkflowTaskManager()
        renew_event = asyncio.Event()
        execution_repository = FakeDriveExecutionRepository(
            events=events,
            snapshot=_snapshot(),
        )
        fms_runtime = FakeFmsRuntime(
            events=events,
            renew_event=renew_event,
        )
        drive_orchestrator = FakeDriveOrchestrator(
            events=events,
            wait_for_event=renew_event,
        )
        service = build_drive_request_service(
            loop=asyncio.get_running_loop(),
            workflow_task_manager=manager,
            task_request_repository=FakeTaskRequestRepository(),
            drive_execution_repository=execution_repository,
            fms_runtime_service=fms_runtime,
            drive_orchestrator=drive_orchestrator,
            fms_reservation_renew_interval_sec=0.001,
        )

        await service.async_create_drive_task(**_drive_payload())
        await asyncio.gather(*manager.tasks)

        assert "renew" in events
        assert events.index("started") < events.index("renew") < events.index("release")
        assert fms_runtime.renewed[0] == {
            "task_id": 3001,
            "robot_id": "pinky1",
            "lease_sec": 30,
        }
        assert execution_repository.results[0]["workflow_response"]["result_code"] == "SUCCESS"

    asyncio.run(_run())


def test_drive_runtime_stops_waiting_retry_when_task_is_cancel_requested():
    async def _run():
        events = []
        manager = FakeWorkflowTaskManager()
        cancelled_snapshot = {
            **_snapshot(),
            "task_status": "CANCEL_REQUESTED",
            "phase": "CANCEL_REQUESTED",
        }
        execution_repository = FakeDriveExecutionRepository(
            events=events,
            snapshot=[_snapshot(), cancelled_snapshot],
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

        assert events == ["snapshot", "reserve", "waiting", "snapshot", "result"]
        assert drive_orchestrator.calls == []
        assert len(fms_runtime.requested) == 1
        assert fms_runtime.released == []
        assert execution_repository.results[0]["workflow_response"]["result_code"] == (
            "CANCELLED"
        )

    asyncio.run(_run())


def test_drive_orchestrator_sends_namespaced_goal_for_each_route_waypoint():
    async def _run():
        navigation = FakeNavigationService()
        orchestrator = DriveOrchestrator(
            nav2_navigation_service=navigation,
            drive_navigation_timeout_sec=42,
        )

        response = await orchestrator.async_run(
            task_id=3001,
            robot_id="pinky3",
            path_snapshot_json=_snapshot()["path_snapshot_json"],
        )

        assert response["result_code"] == "SUCCESS"
        assert [call["robot_id"] for call in navigation.calls] == ["pinky3", "pinky3"]
        assert [call["nav_phase"] for call in navigation.calls] == [
            "DRIVE_WAYPOINT_1",
            "DRIVE_WAYPOINT_2",
        ]
        assert navigation.calls[1]["goal_pose"]["header"]["frame_id"] == "map"
        assert navigation.calls[1]["goal_pose"]["pose"]["position"]["x"] == 1.0

    asyncio.run(_run())


def test_drive_orchestrator_defaults_to_nav2_navigation_service():
    from server.ropi_main_service.application.nav2_navigation import (
        Nav2PoseNavigationService,
    )

    orchestrator = DriveOrchestrator()

    assert isinstance(orchestrator.navigation_service, Nav2PoseNavigationService)
