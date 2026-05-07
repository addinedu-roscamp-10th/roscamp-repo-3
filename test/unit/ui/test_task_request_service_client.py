from server.ropi_main_service.transport.tcp_protocol import (
    MESSAGE_CODE_GUIDE_RESIDENT_EXISTENCE_QUERY,
    MESSAGE_CODE_GUIDE_STAFF_CALL_SUBMISSION,
    MESSAGE_CODE_GUIDE_VISITOR_CARE_HISTORY_QUERY,
    MESSAGE_CODE_GUIDE_VISITOR_REGISTRATION,
    MESSAGE_CODE_PATROL_FALL_EVIDENCE_QUERY,
    MESSAGE_CODE_PATROL_RESUME_TASK,
    MESSAGE_CODE_TASK_STATUS_QUERY,
)
from ui.utils.network import service_clients
from ui.utils.network.service_clients import (
    CaregiverRemoteService,
    CoordinateConfigRemoteService,
    DeliveryRequestRemoteService,
    FmsConfigRemoteService,
    InventoryRemoteService,
    KioskVisitorRemoteService,
    StaffCallRemoteService,
    TaskMonitorRemoteService,
    VisitGuideRemoteService,
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


def test_caregiver_remote_service_exposes_robot_status_bundle_rpc(monkeypatch):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {"summary": {}, "robots": []}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)

    assert CaregiverRemoteService().get_robot_status_bundle() == {
        "summary": {},
        "robots": [],
    }
    assert calls == [("caregiver", "get_robot_status_bundle", {})]


def test_caregiver_remote_service_exposes_alert_log_bundle_rpc(monkeypatch):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {"summary": {}, "events": []}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)

    assert CaregiverRemoteService().get_alert_log_bundle(
        period="LAST_24_HOURS",
        severity="ERROR",
        source_component="Control Service",
        task_id="1001",
        robot_id="pinky2",
        event_type="TASK_FAILED",
        limit=50,
    ) == {"summary": {}, "events": []}
    assert calls == [
        (
            "caregiver",
            "get_alert_log_bundle",
            {
                "period": "LAST_24_HOURS",
                "severity": "ERROR",
                "source_component": "Control Service",
                "task_id": "1001",
                "robot_id": "pinky2",
                "event_type": "TASK_FAILED",
                "limit": 50,
            },
        )
    ]


def test_inventory_remote_service_exposes_bundle_and_item_id_mutation_rpcs(monkeypatch):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {"result_code": "UPDATED"}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)
    service = InventoryRemoteService()

    assert service.get_inventory_bundle() == {"result_code": "UPDATED"}
    assert service.add_item_quantity(item_id="2", quantity_delta=4) == {
        "result_code": "UPDATED"
    }
    assert service.set_item_quantity(item_id="2", quantity=12) == {
        "result_code": "UPDATED"
    }
    assert calls == [
        ("inventory", "get_inventory_bundle", {}),
        ("inventory", "add_item_quantity", {"item_id": "2", "quantity_delta": 4}),
        ("inventory", "set_item_quantity", {"item_id": "2", "quantity": 12}),
    ]


def test_kiosk_visitor_remote_service_sends_if_gui_008_through_010(monkeypatch):
    calls = []

    def fake_send_request(message_code, payload):
        calls.append((message_code, payload))
        return {"ok": True, "payload": {"result_code": "OK"}}

    monkeypatch.setattr(service_clients, "send_request", fake_send_request)
    service = KioskVisitorRemoteService()

    assert service.lookup_residents(keyword="301", limit=5) == {"result_code": "OK"}
    assert service.register_visit(
        visitor_name="김민수",
        phone_no="010-1111-2222",
        relationship="아들",
        visit_purpose="정기 면회",
        target_member_id=1,
        privacy_agreed=True,
        kiosk_id="lobby_kiosk_01",
    ) == {"result_code": "OK"}
    assert service.get_care_history(visitor_id=42) == {"result_code": "OK"}
    assert calls == [
        (
            MESSAGE_CODE_GUIDE_RESIDENT_EXISTENCE_QUERY,
            {
                "keyword": "301",
                "limit": 5,
            },
        ),
        (
            MESSAGE_CODE_GUIDE_VISITOR_REGISTRATION,
            {
                "visitor_name": "김민수",
                "phone_no": "010-1111-2222",
                "relationship": "아들",
                "visit_purpose": "정기 면회",
                "target_member_id": 1,
                "privacy_agreed": True,
                "kiosk_id": "lobby_kiosk_01",
            },
        ),
        (
            MESSAGE_CODE_GUIDE_VISITOR_CARE_HISTORY_QUERY,
            {
                "visitor_id": 42,
            },
        ),
    ]


def test_staff_call_remote_service_sends_if_gui_011(monkeypatch):
    calls = []

    def fake_send_request(message_code, payload):
        calls.append((message_code, payload))
        return {"ok": True, "payload": {"result_code": "ACCEPTED"}}

    monkeypatch.setattr(service_clients, "send_request", fake_send_request)

    result = StaffCallRemoteService().submit_staff_call(
        call_type="방문 등록 도움",
        description="대상 어르신을 찾는 데 도움이 필요합니다.",
        idempotency_key="idem_staff_001",
        visitor_id=42,
        member_id=None,
        kiosk_id="lobby_kiosk_01",
    )

    assert result == {"result_code": "ACCEPTED"}
    assert calls == [
        (
            MESSAGE_CODE_GUIDE_STAFF_CALL_SUBMISSION,
            {
                "call_type": "방문 등록 도움",
                "description": "대상 어르신을 찾는 데 도움이 필요합니다.",
                "idempotency_key": "idem_staff_001",
                "visitor_id": 42,
                "member_id": None,
                "kiosk_id": "lobby_kiosk_01",
            },
        )
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


def test_task_monitor_remote_service_exposes_common_cancel_rpc(monkeypatch):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {"result_code": "CANCEL_REQUESTED", "task_id": "2001"}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)

    response = TaskMonitorRemoteService().cancel_task(
        task_id="2001",
        caregiver_id=7,
        reason="operator_cancel",
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert calls == [
        (
            "task_request",
            "cancel_task",
            {
                "task_id": "2001",
                "caregiver_id": 7,
                "reason": "operator_cancel",
            },
        )
    ]


def test_task_monitor_remote_service_exposes_task_status_query(monkeypatch):
    calls = []

    def fake_send_request(message_code, payload):
        calls.append((message_code, payload))
        return {
            "ok": True,
            "payload": {
                "result_code": "ACCEPTED",
                "task_id": 3001,
                "task_status": "RUNNING",
            },
        }

    monkeypatch.setattr(service_clients, "send_request", fake_send_request)

    response = TaskMonitorRemoteService().get_task_status(task_id="3001")

    assert response["result_code"] == "ACCEPTED"
    assert calls == [
        (
            MESSAGE_CODE_TASK_STATUS_QUERY,
            {"task_id": "3001"},
        )
    ]


def test_visit_guide_remote_service_exposes_task_status_query(monkeypatch):
    calls = []

    def fake_send_request(message_code, payload):
        calls.append((message_code, payload))
        return {
            "ok": True,
            "payload": {
                "result_code": "ACCEPTED",
                "task_id": 3001,
                "task_status": "RUNNING",
            },
        }

    monkeypatch.setattr(service_clients, "send_request", fake_send_request)

    response = VisitGuideRemoteService().get_task_status(task_id=3001)

    assert response["task_status"] == "RUNNING"
    assert calls == [
        (
            MESSAGE_CODE_TASK_STATUS_QUERY,
            {"task_id": "3001"},
        )
    ]


def test_coordinate_config_remote_service_exposes_active_map_bundle_rpc(monkeypatch):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {"result_code": "OK", "map_profile": {"map_id": "map_test11_0423"}}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)

    response = CoordinateConfigRemoteService().get_active_map_bundle(
        include_disabled=False,
        include_zone_boundaries=False,
        include_patrol_paths=False,
    )

    assert response["result_code"] == "OK"
    assert calls == [
        (
            "coordinate_config",
            "get_active_map_bundle",
            {
                "include_disabled": False,
                "include_zone_boundaries": False,
                "include_patrol_paths": False,
            },
        )
    ]


def test_coordinate_config_remote_service_exposes_operation_zone_mutation_rpcs(
    monkeypatch,
):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {"result_code": "OK"}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)
    service = CoordinateConfigRemoteService()

    service.create_operation_zone(
        zone_id="caregiver_room",
        zone_name="보호사실",
        zone_type="STAFF_STATION",
        is_enabled=True,
    )
    service.update_operation_zone(
        zone_id="caregiver_room",
        expected_revision=1,
        zone_name="보호사실",
        zone_type="STAFF_STATION",
        is_enabled=False,
    )
    boundary_json = {
        "type": "POLYGON",
        "header": {"frame_id": "map"},
        "vertices": [
            {"x": 0.0, "y": 0.0},
            {"x": 1.0, "y": 0.0},
            {"x": 1.0, "y": 1.0},
        ],
    }
    service.update_operation_zone_boundary(
        zone_id="caregiver_room",
        expected_revision=2,
        boundary_json=boundary_json,
    )

    assert calls == [
        (
            "coordinate_config",
            "create_operation_zone",
            {
                "zone_id": "caregiver_room",
                "zone_name": "보호사실",
                "zone_type": "STAFF_STATION",
                "map_id": None,
                "is_enabled": True,
            },
        ),
        (
            "coordinate_config",
            "update_operation_zone",
            {
                "zone_id": "caregiver_room",
                "expected_revision": 1,
                "zone_name": "보호사실",
                "zone_type": "STAFF_STATION",
                "is_enabled": False,
            },
        ),
        (
            "coordinate_config",
            "update_operation_zone_boundary",
            {
                "zone_id": "caregiver_room",
                "expected_revision": 2,
                "boundary_json": boundary_json,
            },
        ),
    ]


def test_coordinate_config_remote_service_exposes_goal_pose_update_rpc(monkeypatch):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {"result_code": "UPDATED"}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)

    response = CoordinateConfigRemoteService().update_goal_pose(
        goal_pose_id="delivery_room_301",
        expected_updated_at="2026-05-02T12:01:00",
        zone_id="room_301",
        purpose="DESTINATION",
        pose_x=1.7,
        pose_y=0.02,
        pose_yaw=0.0,
        frame_id="map",
        is_enabled=True,
    )

    assert response["result_code"] == "UPDATED"
    assert calls == [
        (
            "coordinate_config",
            "update_goal_pose",
            {
                "goal_pose_id": "delivery_room_301",
                "expected_updated_at": "2026-05-02T12:01:00",
                "zone_id": "room_301",
                "purpose": "DESTINATION",
                "pose_x": 1.7,
                "pose_y": 0.02,
                "pose_yaw": 0.0,
                "frame_id": "map",
                "is_enabled": True,
            },
        )
    ]


def test_coordinate_config_remote_service_exposes_patrol_area_path_update_rpc(
    monkeypatch,
):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {"result_code": "UPDATED"}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)
    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 0.0},
        ],
    }

    response = CoordinateConfigRemoteService().update_patrol_area_path(
        patrol_area_id="patrol_ward_night_01",
        expected_revision=7,
        path_json=path_json,
    )

    assert response["result_code"] == "UPDATED"
    assert calls == [
        (
            "coordinate_config",
            "update_patrol_area_path",
            {
                "patrol_area_id": "patrol_ward_night_01",
                "expected_revision": 7,
                "path_json": path_json,
            },
        )
    ]


def test_coordinate_config_remote_service_exposes_patrol_area_create_and_update_rpc(
    monkeypatch,
):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {
            "result_code": "CREATED" if method == "create_patrol_area" else "UPDATED"
        }

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)
    path_json = {
        "header": {"frame_id": "map"},
        "poses": [
            {"x": 0.0, "y": 0.0, "yaw": 0.0},
            {"x": 1.0, "y": 1.0, "yaw": 0.0},
        ],
    }
    service = CoordinateConfigRemoteService()

    create_response = service.create_patrol_area(
        patrol_area_id="patrol_day_01",
        map_id="map_test12_0506",
        patrol_area_name="주간 병동 순찰",
        path_json=path_json,
        is_enabled=True,
    )
    update_response = service.update_patrol_area(
        patrol_area_id="patrol_day_01",
        map_id="map_test12_0506",
        expected_revision=1,
        patrol_area_name="주간 병동 순찰",
        path_json=path_json,
        is_enabled=False,
    )

    assert create_response["result_code"] == "CREATED"
    assert update_response["result_code"] == "UPDATED"
    assert calls == [
        (
            "coordinate_config",
            "create_patrol_area",
            {
                "patrol_area_id": "patrol_day_01",
                "map_id": "map_test12_0506",
                "patrol_area_name": "주간 병동 순찰",
                "path_json": path_json,
                "is_enabled": True,
            },
        ),
        (
            "coordinate_config",
            "update_patrol_area",
            {
                "patrol_area_id": "patrol_day_01",
                "map_id": "map_test12_0506",
                "expected_revision": 1,
                "patrol_area_name": "주간 병동 순찰",
                "path_json": path_json,
                "is_enabled": False,
            },
        ),
    ]


def test_coordinate_config_remote_service_exposes_map_asset_rpc(monkeypatch):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {"result_code": "OK", "asset_type": "YAML"}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)

    response = CoordinateConfigRemoteService().get_map_asset(
        asset_type="YAML",
        map_id="map_test11_0423",
        encoding="TEXT",
    )

    assert response["result_code"] == "OK"
    assert calls == [
        (
            "coordinate_config",
            "get_map_asset",
            {
                "asset_type": "YAML",
                "map_id": "map_test11_0423",
                "encoding": "TEXT",
            },
        )
    ]


def test_fms_config_remote_service_exposes_waypoint_bundle_and_upsert(monkeypatch):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return {"result_code": "OK", "waypoints": []}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)

    service = FmsConfigRemoteService()

    assert (
        service.get_active_graph_bundle(
            include_disabled=False,
            include_edges=False,
            include_routes=False,
            include_reservations=True,
        )["result_code"]
        == "OK"
    )
    assert (
        service.upsert_waypoint(
            waypoint_id="corridor_01",
            expected_updated_at=None,
            display_name="복도1",
            waypoint_type="CORRIDOR",
            pose_x=0.1,
            pose_y=-0.2,
            pose_yaw=1.57,
            frame_id="map",
            snap_group="main_corridor",
            is_enabled=True,
        )["result_code"]
        == "OK"
    )
    assert (
        service.upsert_edge(
            edge_id="edge_corridor_01_02",
            expected_updated_at="2026-05-04T10:04:00Z",
            from_waypoint_id="corridor_01",
            to_waypoint_id="corridor_02",
            is_bidirectional=True,
            traversal_cost=1.5,
            priority=10,
            is_enabled=True,
        )["result_code"]
        == "OK"
    )
    assert (
        service.upsert_route(
            route_id="route_corridor_01_02",
            expected_revision=1,
            route_name="복도 1-2",
            route_scope="COMMON",
            waypoint_sequence=[
                {"waypoint_id": "corridor_01"},
                {"waypoint_id": "corridor_02"},
            ],
            is_enabled=True,
        )["result_code"]
        == "OK"
    )

    assert calls == [
        (
            "fms_config",
            "get_active_graph_bundle",
            {
                "include_disabled": False,
                "include_edges": False,
                "include_routes": False,
                "include_reservations": True,
            },
        ),
        (
            "fms_config",
            "upsert_waypoint",
            {
                "waypoint_id": "corridor_01",
                "expected_updated_at": None,
                "display_name": "복도1",
                "waypoint_type": "CORRIDOR",
                "pose_x": 0.1,
                "pose_y": -0.2,
                "pose_yaw": 1.57,
                "frame_id": "map",
                "snap_group": "main_corridor",
                "is_enabled": True,
            },
        ),
        (
            "fms_config",
            "upsert_edge",
            {
                "edge_id": "edge_corridor_01_02",
                "expected_updated_at": "2026-05-04T10:04:00Z",
                "from_waypoint_id": "corridor_01",
                "to_waypoint_id": "corridor_02",
                "is_bidirectional": True,
                "traversal_cost": 1.5,
                "priority": 10,
                "is_enabled": True,
            },
        ),
        (
            "fms_config",
            "upsert_route",
            {
                "route_id": "route_corridor_01_02",
                "expected_revision": 1,
                "route_name": "복도 1-2",
                "route_scope": "COMMON",
                "waypoint_sequence": [
                    {"waypoint_id": "corridor_01"},
                    {"waypoint_id": "corridor_02"},
                ],
                "is_enabled": True,
            },
        ),
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


def test_visit_guide_remote_service_exposes_start_guide_driving_rpc(monkeypatch):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return True, "안내 주행을 시작했습니다.", {"result_code": "ACCEPTED"}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)

    response = VisitGuideRemoteService().start_guide_driving(
        task_id="3001",
        pinky_id="pinky1",
        target_track_id=17,
    )

    assert response[0] is True
    assert calls == [
        (
            "visit_guide",
            "start_guide_driving",
            {
                "task_id": "3001",
                "target_track_id": 17,
                "pinky_id": "pinky1",
            },
        )
    ]


def test_visit_guide_remote_service_finish_uses_common_task_cancel_rpc(monkeypatch):
    calls = []

    def fake_rpc(service, method, **kwargs):
        calls.append((service, method, kwargs))
        return True, "취소 요청이 접수되었습니다.", {"result_code": "CANCEL_REQUESTED"}

    monkeypatch.setattr(service_clients, "_rpc", fake_rpc)

    response = VisitGuideRemoteService().finish_guide_session(
        task_id="3001",
        pinky_id="pinky1",
        finish_reason="USER_CANCELLED",
    )

    assert response[0] is True
    assert calls == [
        (
            "task_request",
            "cancel_task",
            {
                "task_id": "3001",
                "caregiver_id": None,
                "reason": "USER_CANCELLED",
            },
        )
    ]


def test_visit_guide_remote_service_does_not_expose_retired_tracking_status_rpc():
    assert not hasattr(VisitGuideRemoteService(), "get_tracking_status")
