from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY,
    MESSAGE_CODE_PATROL_RESUME_TASK,
)
from ui.utils.network import service_clients
from ui.utils.network.service_clients import (
    DeliveryRequestRemoteService,
    TaskMonitorRemoteService,
)


def test_delivery_request_remote_service_exposes_option_rpc_methods(monkeypatch):
    calls = []

    def fake_rpc(self, method, **kwargs):
        calls.append((method, kwargs))
        return [{"ok": True}]

    monkeypatch.setattr(DeliveryRequestRemoteService, "_rpc", fake_rpc)

    service = DeliveryRequestRemoteService()

    assert service.get_delivery_destinations() == [{"ok": True}]
    assert service.get_patrol_areas() == [{"ok": True}]
    assert calls == [
        ("get_delivery_destinations", {}),
        ("get_patrol_areas", {}),
    ]


def test_delivery_request_remote_service_exposes_cancel_rpc(monkeypatch):
    calls = []

    def fake_rpc(self, method, **kwargs):
        calls.append((method, kwargs))
        return {"result_code": "CANCEL_REQUESTED"}

    monkeypatch.setattr(DeliveryRequestRemoteService, "_rpc", fake_rpc)

    service = DeliveryRequestRemoteService()

    assert service.cancel_delivery_task(1001) == {"result_code": "CANCEL_REQUESTED"}
    assert calls == [
        (
            "cancel_delivery_task",
            {
                "task_id": "1001",
            },
        )
    ]


def test_delivery_request_remote_service_sends_patrol_resume_over_if_pat_002(
    monkeypatch,
):
    calls = []

    def fake_send_request(message_code, payload):
        calls.append((message_code, payload))
        return {
            "ok": True,
            "payload": {
                "result_code": "ACCEPTED",
                "task_id": "2001",
                "task_status": "RUNNING",
            },
        }

    monkeypatch.setattr(service_clients, "send_request", fake_send_request)

    response = DeliveryRequestRemoteService().resume_patrol_task(
        task_id="2001",
        caregiver_id=7,
        member_id=301,
        action_memo="119 신고 후 병원 이송",
    )

    assert response["result_code"] == "ACCEPTED"
    assert calls == [
        (
            MESSAGE_CODE_PATROL_RESUME_TASK,
            {
                "task_id": "2001",
                "caregiver_id": 7,
                "member_id": 301,
                "action_memo": "119 신고 후 병원 이송",
            },
        )
    ]


def test_task_monitor_remote_service_exposes_snapshot_rpc(monkeypatch):
    calls = []

    def fake_rpc(self, method, **kwargs):
        calls.append((method, kwargs))
        return {"result_code": "ACCEPTED", "last_event_seq": 12, "tasks": []}

    monkeypatch.setattr(TaskMonitorRemoteService, "_rpc", fake_rpc)

    response = TaskMonitorRemoteService().get_task_monitor_snapshot(
        consumer_id="ui-test",
        task_types=["PATROL"],
        statuses=["RUNNING"],
        include_recent_terminal=False,
        recent_terminal_limit=3,
        limit=5,
    )

    assert response["last_event_seq"] == 12
    assert calls == [
        (
            "get_task_monitor_snapshot",
            {
                "consumer_id": "ui-test",
                "task_types": ["PATROL"],
                "statuses": ["RUNNING"],
                "include_recent_terminal": False,
                "recent_terminal_limit": 3,
                "limit": 5,
            },
        )
    ]


def test_task_monitor_remote_service_sends_fall_evidence_over_if_pat_007(monkeypatch):
    calls = []

    def fake_send_request(message_code, payload):
        calls.append((message_code, payload))
        return {
            "ok": True,
            "payload": {"result_code": "OK", "evidence_image_id": "fall-1"},
        }

    monkeypatch.setattr(service_clients, "send_request", fake_send_request)

    response = TaskMonitorRemoteService().get_fall_evidence_image(
        consumer_id="ui-test",
        task_id="2001",
        alert_id="17",
        evidence_image_id="fall-1",
        result_seq=541,
    )

    assert response["result_code"] == "OK"
    assert calls == [
        (
            MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY,
            {
                "consumer_id": "ui-test",
                "task_id": "2001",
                "alert_id": "17",
                "evidence_image_id": "fall-1",
                "result_seq": 541,
            },
        )
    ]
