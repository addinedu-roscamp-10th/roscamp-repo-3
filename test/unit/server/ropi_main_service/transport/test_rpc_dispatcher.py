import asyncio

from server.ropi_main_service.transport.rpc_dispatcher import ControlRpcDispatcher


class FakeTaskMonitorService:
    def get_task_monitor_snapshot(self):
        return {"result_code": "ACCEPTED", "tasks": []}


class FakeGuideService:
    async def async_send_guide_command(self, **payload):
        return True, "안내 제어 명령이 수락되었습니다.", {
            "result_code": "ACCEPTED",
            "task_id": payload["task_id"],
            "task_type": "GUIDE",
            "task_status": "RUNNING",
            "phase": "WAIT_TARGET_TRACKING",
            "assigned_robot_id": payload["pinky_id"],
        }


class FakeTaskRequestService:
    def cancel_task(self, **payload):
        return {
            "result_code": "ACCEPTED",
            "task_id": payload["task_id"],
            "task_status": "CANCEL_REQUESTED",
        }


def test_control_rpc_dispatcher_returns_unknown_service_error():
    dispatcher = ControlRpcDispatcher(service_registry={})

    result = dispatcher.dispatch(
        {
            "service": "missing",
            "method": "anything",
            "kwargs": {},
        }
    )

    assert result.ok is False
    assert result.error_code == "UNKNOWN_SERVICE"
    assert "missing" in result.error_message


def test_control_rpc_dispatcher_attaches_task_monitor_handoff_sequence():
    dispatcher = ControlRpcDispatcher(
        service_registry={"task_monitor": FakeTaskMonitorService},
        task_monitor_watermark_provider=lambda: 91,
    )

    result = dispatcher.dispatch(
        {
            "service": "task_monitor",
            "method": "get_task_monitor_snapshot",
            "kwargs": {},
        }
    )

    assert result.ok is True
    assert result.payload == {
        "result_code": "ACCEPTED",
        "tasks": [],
        "last_event_seq": 91,
    }


def test_control_rpc_dispatcher_async_publishes_guide_command_task_update():
    published = []

    async def publish_task_update(response, *, source, task_type=None):
        published.append(
            {
                "response": response,
                "source": source,
                "task_type": task_type,
            }
        )

    dispatcher = ControlRpcDispatcher(
        service_registry={"visit_guide": FakeGuideService},
        task_update_publisher=publish_task_update,
    )

    result = asyncio.run(
        dispatcher.async_dispatch(
            {
                "service": "visit_guide",
                "method": "send_guide_command",
                "kwargs": {
                    "task_id": "3001",
                    "pinky_id": "pinky1",
                    "command_type": "WAIT_TARGET_TRACKING",
                },
            }
        )
    )

    assert result.ok is True
    assert result.payload[0] is True
    assert published == [
        {
            "response": result.payload[2],
            "source": "GUIDE_COMMAND",
            "task_type": "GUIDE",
        }
    ]


def test_control_rpc_dispatcher_async_publishes_cancel_task_update():
    published = []

    async def publish_task_update(response, *, source, task_type=None):
        published.append(
            {
                "response": response,
                "source": source,
                "task_type": task_type,
            }
        )

    dispatcher = ControlRpcDispatcher(
        service_registry={"task_request": FakeTaskRequestService},
        task_update_publisher=publish_task_update,
    )

    result = asyncio.run(
        dispatcher.async_dispatch(
            {
                "service": "task_request",
                "method": "cancel_task",
                "kwargs": {"task_id": "3001"},
            }
        )
    )

    assert result.ok is True
    assert published == [
        {
            "response": result.payload,
            "source": "TASK_CANCEL",
            "task_type": None,
        }
    ]
