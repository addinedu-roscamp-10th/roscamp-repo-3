# ruff: noqa: E402
import os
import json
import uuid

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest_plugins = ("runtime_db_seeders", "runtime_servers")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from server.ropi_main_service.persistence.connection import fetch_one, get_connection
from server.ropi_main_service.persistence.repositories.task_request_repository import DeliveryRequestRepository
from runtime_waiting import wait_for_condition, wait_for_qt
from ui.utils.network import tcp_client
from ui.utils.network.service_clients import (
    DeliveryRequestRemoteService,
    TaskMonitorRemoteService,
    VisitGuideRemoteService,
)
from ui.kiosk_ui.main_window import KioskHomeWindow
from ui.utils.network.tcp_client import send_request
from ui.utils.pages.caregiver.task_request_page import TaskRequestPage
from ui.utils.session.session_manager import SessionManager, UserSession

SERVER_HOST = "127.0.0.1"


def safe_fetch_one(query: str):
    try:
        return fetch_one(query)
    except Exception:
        return None


def build_if_del_001_payload() -> dict:
    products = DeliveryRequestRepository().get_all_products()
    assert products, "The remote DB has no item rows for IF-DEL-001 integration testing."

    product = products[0]

    caregiver_row = safe_fetch_one(
        "SELECT CAST(caregiver_id AS CHAR) AS caregiver_id FROM caregiver LIMIT 1"
    )
    return {
        "request_id": "runtime-if-del-001",
        "caregiver_id": (
            caregiver_row["caregiver_id"] if caregiver_row else "1"
        ),
        "item_id": product["item_id"],
        "quantity": 1,
        "destination_id": "delivery_room_301",
        "priority": "NORMAL",
        "notes": "runtime integration test",
        "idempotency_key": "runtime-if-del-001-idem",
    }


def build_runtime_caregiver_session() -> UserSession:
    payload = build_if_del_001_payload()
    return UserSession(
        user_id=payload["caregiver_id"],
        name="runtime-caregiver",
        role="caregiver",
    )


def _visible_texts(widget) -> list[str]:
    texts: list[str] = []
    for label in widget.findChildren(QLabel):
        texts.append(label.text())
    for button in widget.findChildren(QPushButton):
        texts.append(button.text())
    return texts


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def patched_ui_endpoint(runtime_control_server, monkeypatch):
    monkeypatch.setattr(tcp_client, "CONTROL_SERVER_HOST", SERVER_HOST)
    monkeypatch.setattr(tcp_client, "CONTROL_SERVER_PORT", runtime_control_server["port"])
    monkeypatch.setattr(tcp_client, "CONTROL_SERVER_TIMEOUT", 5.0)
    return runtime_control_server


def test_server_process_heartbeat_reports_db_status(patched_ui_endpoint):
    response = send_request("HEARTBEAT", {"check_db": True}, timeout=5.0)

    assert response["ok"] is True
    assert response["payload"]["message"] == "메인 서버 연결 정상"
    assert response["payload"]["db"]["ok"] is True


def test_control_server_subscribes_ai_fall_stream_and_starts_fall_alert(
    control_server_with_ai_fall_stream,
    ai_fall_stream_server,
    active_patrol_task_seed,
):
    assert control_server_with_ai_fall_stream["port"] > 0
    assert ai_fall_stream_server["subscribed"].wait(timeout=10)

    with ai_fall_stream_server["request_lock"]:
        requests = list(ai_fall_stream_server["requests"])

    assert requests
    assert requests[0]["consumer_id"] == "control_service_ai_fall"
    assert "pinky_id" not in requests[0]
    assert requests[0]["last_seq"] == 0

    ai_fall_stream_server["push_requested"].set()
    task_id = active_patrol_task_seed["task_id"]

    updated = wait_for_condition(
        lambda: (
            safe_fetch_one(
                "SELECT phase FROM task "
                f"WHERE task_id = {int(task_id)}"
            )
            or {}
        ).get("phase")
        == "WAIT_FALL_RESPONSE",
        timeout=10.0,
    )
    if not updated:
        process = control_server_with_ai_fall_stream["process"]
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        pytest.fail(
            "Control Service did not process the PAT-005 push.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

    task_row = safe_fetch_one(
        "SELECT phase, latest_reason_code FROM task "
        f"WHERE task_id = {int(task_id)}"
    )
    patrol_row = safe_fetch_one(
        "SELECT patrol_status FROM patrol_task_detail "
        f"WHERE task_id = {int(task_id)}"
    )
    inference_row = safe_fetch_one(
        "SELECT robot_id, result_json FROM ai_inference_log "
        f"WHERE task_id = {int(task_id)} ORDER BY ai_inference_log_id DESC LIMIT 1"
    )

    assert task_row["phase"] == "WAIT_FALL_RESPONSE"
    assert task_row["latest_reason_code"] == "FALL_DETECTED"
    assert patrol_row["patrol_status"] == "WAITING_FALL_RESPONSE"
    assert inference_row["robot_id"] == "pinky3"
    assert json.loads(inference_row["result_json"])["pinky_id"] == "pinky3"


def test_kiosk_client_queries_single_guide_task_status(
    patched_ui_endpoint,
    waiting_guide_task_seed,
):
    del patched_ui_endpoint

    payload = VisitGuideRemoteService().get_task_status(
        task_id=waiting_guide_task_seed["task_id"],
    )

    assert payload["result_code"] == "ACCEPTED"
    assert payload["task_id"] == waiting_guide_task_seed["task_id"]
    assert payload["task_type"] == "GUIDE"
    assert payload["task_status"] == "RUNNING"
    assert payload["phase"] == "WAIT_TARGET_TRACKING"
    assert payload["assigned_robot_id"] == "pinky1"


def test_ui_client_fall_evidence_query_hits_real_server_and_ai_mock(
    patched_ui_endpoint,
    fall_evidence_seed,
    ai_evidence_server,
):
    with ai_evidence_server["request_lock"]:
        request_count_before = len(ai_evidence_server["requests"])

    response = TaskMonitorRemoteService().get_fall_evidence_image(
        consumer_id="ui-integration-task-monitor",
        task_id=fall_evidence_seed["task_id"],
        alert_id=fall_evidence_seed["alert_id"],
        evidence_image_id=fall_evidence_seed["evidence_image_id"],
        result_seq=fall_evidence_seed["result_seq"],
    )

    assert response["result_code"] == "OK", json.dumps(response, ensure_ascii=False)
    assert response["task_id"] == fall_evidence_seed["task_id"]
    assert response["alert_id"] == fall_evidence_seed["alert_id"]
    assert response["evidence_image_id"] == fall_evidence_seed["evidence_image_id"]
    assert response["image_width_px"] == 640
    assert response["detections"][0]["class_name"] == "fall"

    with ai_evidence_server["request_lock"]:
        ai_requests = ai_evidence_server["requests"][request_count_before:]

    assert ai_requests == [
        {
            "consumer_id": "control_service_ai_fall",
            "evidence_image_id": fall_evidence_seed["evidence_image_id"],
            "result_seq": fall_evidence_seed["result_seq"],
            **(
                {"pinky_id": fall_evidence_seed["robot_id"]}
                if fall_evidence_seed["robot_id"]
                else {}
            ),
        }
    ]


def test_ui_client_cancel_patrol_task_hits_real_server_and_db(
    patched_ui_endpoint,
    active_patrol_task_seed,
):
    task_id = active_patrol_task_seed["task_id"]

    response = TaskMonitorRemoteService().cancel_task(
        task_id=task_id,
        caregiver_id=7,
        reason="operator_cancel",
    )

    assert response["result_code"] == "CANCEL_REQUESTED"
    assert response["task_id"] == task_id
    assert response["task_type"] == "PATROL"
    assert response["task_status"] == "CANCEL_REQUESTED"
    assert response["cancel_requested"] is True

    task_row = safe_fetch_one(
        "SELECT task_status, phase, latest_reason_code FROM task "
        f"WHERE task_id = {int(task_id)}"
    )
    patrol_row = safe_fetch_one(
        "SELECT patrol_status FROM patrol_task_detail "
        f"WHERE task_id = {int(task_id)}"
    )
    event_row = safe_fetch_one(
        "SELECT event_name, reason_code FROM task_event_log "
        f"WHERE task_id = {int(task_id)} "
        "ORDER BY task_event_log_id DESC LIMIT 1"
    )

    assert task_row["task_status"] == "CANCEL_REQUESTED"
    assert task_row["phase"] == "CANCEL_REQUESTED"
    assert task_row["latest_reason_code"] == "USER_CANCEL_REQUESTED"
    assert patrol_row["patrol_status"] == "CANCEL_REQUESTED"
    assert event_row["event_name"] == "PATROL_TASK_CANCEL_REQUESTED"
    assert event_row["reason_code"] == "USER_CANCEL_REQUESTED"


def test_ui_client_create_delivery_task_hits_real_server(patched_ui_endpoint, runtime_delivery_schema):
    payload = build_if_del_001_payload()

    response = DeliveryRequestRemoteService().create_delivery_task(**payload)

    assert response["result_code"] == "ACCEPTED"
    assert isinstance(response["task_id"], int)
    assert response["task_status"] == "WAITING_DISPATCH"
    assert response["assigned_robot_id"] == "pinky2"


def test_kiosk_create_guide_task_hits_real_server_and_db(
    patched_ui_endpoint,
    guide_destination_seed,
):
    visitor_row = guide_destination_seed
    request_id = f"runtime-if-gui-001-{uuid.uuid4().hex}"
    response = send_request(
        "GUIDE_CREATE_TASK",
        {
            "request_id": request_id,
            "visitor_id": int(visitor_row["visitor_id"]),
            "idempotency_key": f"{request_id}-idem",
        },
        timeout=5.0,
    )

    assert response["ok"] is True
    payload = response["payload"]
    assert payload["result_code"] == "ACCEPTED", payload
    task_id = int(payload["task_id"])

    try:
        assert payload["task_status"] == "WAITING_DISPATCH"
        assert payload["phase"] == "WAIT_GUIDE_START_CONFIRM"
        assert payload["destination_id"] == visitor_row["goal_pose_id"]
        assert payload["destination_map_id"] == visitor_row["map_id"]

        task_row = safe_fetch_one(
            "SELECT task_type, requester_type, requester_id, task_status, phase, map_id "
            f"FROM task WHERE task_id = {task_id}"
        )
        guide_row = safe_fetch_one(
            "SELECT visitor_id, member_id, destination_goal_pose_id, guide_phase "
            f"FROM guide_task_detail WHERE task_id = {task_id}"
        )
        event_row = safe_fetch_one(
            "SELECT event_name, result_code FROM task_event_log "
            f"WHERE task_id = {task_id} ORDER BY task_event_log_id DESC LIMIT 1"
        )

        assert task_row["task_type"] == "GUIDE"
        assert task_row["requester_type"] == "VISITOR"
        assert task_row["requester_id"] == str(visitor_row["visitor_id"])
        assert task_row["task_status"] == "WAITING_DISPATCH"
        assert task_row["phase"] == "WAIT_GUIDE_START_CONFIRM"
        assert task_row["map_id"] == visitor_row["map_id"]
        assert int(guide_row["visitor_id"]) == int(visitor_row["visitor_id"])
        assert int(guide_row["member_id"]) == int(visitor_row["member_id"])
        assert guide_row["destination_goal_pose_id"] == visitor_row["goal_pose_id"]
        assert guide_row["guide_phase"] == "WAIT_GUIDE_START_CONFIRM"
        assert event_row["event_name"] == "GUIDE_TASK_ACCEPTED"
        assert event_row["result_code"] == "ACCEPTED"

        start_ok, start_message, start_payload = (
            VisitGuideRemoteService().send_guide_command(
                task_id=task_id,
                pinky_id=payload["assigned_robot_id"],
                command_type="WAIT_TARGET_TRACKING",
            )
        )
        assert start_ok is True
        assert start_message == "안내 제어 명령이 수락되었습니다."
        assert start_payload["task_status"] == "RUNNING"
        assert start_payload["phase"] == "WAIT_TARGET_TRACKING"
        assert start_payload["guide_phase"] == "WAIT_TARGET_TRACKING"

        running_task_row = safe_fetch_one(
            "SELECT task_status, phase, started_at FROM task "
            f"WHERE task_id = {task_id}"
        )
        running_guide_row = safe_fetch_one(
            "SELECT guide_phase FROM guide_task_detail "
            f"WHERE task_id = {task_id}"
        )
        running_event_row = safe_fetch_one(
            "SELECT event_name, result_code FROM task_event_log "
            f"WHERE task_id = {task_id} ORDER BY task_event_log_id DESC LIMIT 1"
        )

        assert running_task_row["task_status"] == "RUNNING"
        assert running_task_row["phase"] == "WAIT_TARGET_TRACKING"
        assert running_task_row["started_at"] is not None
        assert running_guide_row["guide_phase"] == "WAIT_TARGET_TRACKING"
        assert running_event_row["event_name"] == "GUIDE_COMMAND_ACCEPTED"
        assert running_event_row["result_code"] == "ACCEPTED"

        driving_ok, driving_message, driving_payload = (
            VisitGuideRemoteService().start_guide_driving(
                task_id=task_id,
                pinky_id=payload["assigned_robot_id"],
                target_track_id=17,
            )
        )
        assert driving_ok is True
        assert driving_message == "안내 주행을 시작했습니다."
        assert driving_payload["task_status"] == "RUNNING"
        assert driving_payload["phase"] == "GUIDANCE_RUNNING"
        assert driving_payload["target_track_id"] == 17
        assert driving_payload["command_response"]["accepted"] is True

        driving_task_row = safe_fetch_one(
            "SELECT task_status, phase FROM task "
            f"WHERE task_id = {task_id}"
        )
        driving_guide_row = safe_fetch_one(
            "SELECT guide_phase, target_track_id FROM guide_task_detail "
            f"WHERE task_id = {task_id}"
        )

        assert driving_task_row["task_status"] == "RUNNING"
        assert driving_task_row["phase"] == "GUIDANCE_RUNNING"
        assert driving_guide_row["guide_phase"] == "GUIDANCE_RUNNING"
        assert driving_guide_row["target_track_id"] == 17
    finally:
        cleanup_conn = get_connection()
        try:
            with cleanup_conn.cursor() as cursor:
                cursor.execute("DELETE FROM task WHERE task_id = %s", (task_id,))
        finally:
            cleanup_conn.close()


def test_task_request_page_loads_items_from_real_server(patched_ui_endpoint, qapp, runtime_delivery_schema):
    page = TaskRequestPage()
    page.show()

    try:
        loaded = wait_for_qt(
            qapp,
            lambda: (
                page.delivery_form.load_thread is None
                and page.delivery_form.item_combo.count() > 0
            ),
            timeout=10.0,
        )

        assert loaded is True, "TaskRequestPage did not finish loading items."
        assert page.delivery_form.item_combo.isEnabled() is True
        assert page.delivery_form.submit_btn.isEnabled() is True
        assert page.delivery_form.item_combo.itemText(0) != "물품 목록 불러오기 실패"
        assert page.delivery_form.item_combo.itemText(0) != "등록된 물품 없음"
    finally:
        page.close()
        wait_for_qt(qapp, lambda: True, timeout=0.1)


def test_kiosk_visitor_registration_lookup_and_register_hits_real_server_and_db(
    patched_ui_endpoint,
    qapp,
):
    member_row = safe_fetch_one(
        """
        SELECT member_id, member_name, room_no, birth_date
        FROM member
        WHERE room_no IS NOT NULL
        ORDER BY member_id
        LIMIT 1
        """
    )
    assert member_row is not None, "The runtime DB has no resident rows."

    window = KioskHomeWindow()
    window.show()

    try:
        window.home_page.register_card.clicked.emit()
        assert window.stack.currentWidget() is window.registration_page

        page = window.registration_page
        page.visitor_name_input.setText("통합테스트방문자")
        page.phone_input.setText("010-9999-0001")
        page.relationship_input.setText("보호자")
        page.select_visit_purpose("family")
        page.privacy_checkbox.setChecked(True)
        page.resident_search_input.setText(str(member_row["room_no"]))
        page.search_resident()

        assert page.selected_resident is not None
        assert page.selected_resident["member_id"] == int(member_row["member_id"])
        assert page.selected_resident["birth_date"] == str(member_row["birth_date"])
        assert page.selected_resident["room_no"] == str(member_row["room_no"])
        assert "어르신" in page.resident_name_label.text()
        assert f"{member_row['room_no']}호" in " ".join(_visible_texts(page))

        page.register_visit()

        assert page.visitor_session is not None
        assert page.visitor_session["member_id"] == int(member_row["member_id"])
        assert isinstance(page.visitor_session["visitor_id"], int)
        assert window.stack.currentWidget() is window.confirmation_page
    finally:
        window.close()
        wait_for_qt(qapp, lambda: True, timeout=0.1)


def test_kiosk_staff_call_home_hits_real_server_and_db(patched_ui_endpoint, qapp):
    window = KioskHomeWindow()
    window.show()

    try:
        window.home_page.call_card.clicked.emit()

        assert window.staff_call_modal.isVisible() is True
        assert "직원 호출이 접수되었습니다." in _visible_texts(window.staff_call_modal)

        row = safe_fetch_one(
            """
            SELECT call_type, description, visitor_id, member_id, kiosk_id
            FROM kiosk_staff_call_log
            WHERE kiosk_id = 'lobby_kiosk_01'
            ORDER BY kiosk_staff_call_id DESC
            LIMIT 1
            """
        )
        assert row is not None
        assert row["call_type"] == "직원 호출"
        assert "홈 화면" in row["description"]
        assert row["visitor_id"] is None
        assert row["member_id"] is None
        assert row["kiosk_id"] == "lobby_kiosk_01"
    finally:
        window.close()
        wait_for_qt(qapp, lambda: True, timeout=0.1)


def test_task_request_page_submit_request_hits_if_del_001(patched_ui_endpoint, qapp, runtime_delivery_schema):
    SessionManager.login(build_runtime_caregiver_session())
    page = TaskRequestPage()
    page.show()

    try:
        loaded = wait_for_qt(
            qapp,
            lambda: (
                page.delivery_form.load_thread is None
                and page.delivery_form.item_combo.count() > 0
                and page.delivery_form.item_combo.isEnabled()
            ),
            timeout=10.0,
        )
        assert loaded is True, "TaskRequestPage did not finish loading items."

        page.delivery_form.quantity_input.setValue(2)
        page.delivery_form.priority_combo.setCurrentText("긴급")
        page.delivery_form.destination_combo.setCurrentIndex(0)
        page.delivery_form.detail_input.setPlainText("runtime submit test")
        page.delivery_form.submit_request()

        submitted = wait_for_qt(
            qapp,
            lambda: (
                page.delivery_form.submit_thread is None
                and page.delivery_form.load_thread is None
            ),
            timeout=10.0,
        )
        assert submitted is True, "Delivery submit or refresh worker did not finish."
        assert page.delivery_form.status_label.isVisible() is True
        assert "접수되었습니다" in page.delivery_form.status_label.text()
    finally:
        page.close()
        SessionManager.logout()
        wait_for_qt(qapp, lambda: True, timeout=0.1)
