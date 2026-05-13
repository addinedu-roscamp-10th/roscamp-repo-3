import os
import tomllib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QFrame,
    QTableWidget,
)


_APP = None
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _display_texts(widget) -> list[str]:
    label_texts = [label.text() for label in widget.findChildren(QLabel)]
    button_texts = [button.text() for button in widget.findChildren(QPushButton)]
    placeholder_texts = [
        line_edit.placeholderText() for line_edit in widget.findChildren(QLineEdit)
    ]
    table_texts: list[str] = []
    for table in widget.findChildren(QTableWidget):
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                if item is not None:
                    table_texts.append(item.text())
    plain_texts = [
        text.toPlainText() for text in widget.findChildren(QPlainTextEdit)
    ]
    return label_texts + button_texts + placeholder_texts + table_texts + plain_texts


def test_admin_demo_fixture_uses_ropi_product_labels_and_korean_values():
    from ui.presentation_demo.admin_demo_data import (
        build_admin_demo_snapshot,
        forbidden_internal_tokens,
        forbidden_raw_enum_tokens,
        visible_snapshot_texts,
    )

    snapshot = build_admin_demo_snapshot()

    assert [robot.display_id for robot in snapshot.robots] == [
        "ROPI 1",
        "ROPI 2",
        "ROPI 3",
    ]
    assert [marker.display_id for marker in snapshot.map_markers] == [
        "ROPI 1",
        "ROPI 2",
        "ROPI 3",
    ]
    assert len(snapshot.map_markers) == 3
    marker_by_id = {marker.display_id: marker for marker in snapshot.map_markers}
    assert (marker_by_id["ROPI 2"].x, marker_by_id["ROPI 2"].y) == (0.40, -0.36)
    assert (marker_by_id["ROPI 1"].x, marker_by_id["ROPI 1"].y) == (0.78, 0.04)
    assert (marker_by_id["ROPI 3"].x, marker_by_id["ROPI 3"].y) == (1.36, -0.46)

    visible_text = " ".join(visible_snapshot_texts(snapshot))
    lowered = visible_text.lower()
    assert all(token not in lowered for token in forbidden_internal_tokens())
    assert all(token not in visible_text for token in forbidden_raw_enum_tokens())
    assert {"안내", "운반", "순찰", "진행 중", "주의"}.issubset(
        set(visible_snapshot_texts(snapshot))
    )


def test_admin_demo_window_has_home_presentation_and_production_pages():
    _app()

    from ui.presentation_demo.admin_demo_app import create_demo_window
    from ui.presentation_demo.admin_demo_app import (
        PresentationAlertsLogPage,
        PresentationTaskMonitorPage,
    )
    from ui.utils.pages.caregiver.alert_log_page import AlertLogPage
    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage
    from ui.utils.pages.caregiver.task_request_page import TaskRequestPage

    window = create_demo_window(autostart_runtime=False)

    try:
        texts = _display_texts(window)
        text_blob = " ".join(texts)
        lowered = text_blob.lower()

        assert window.NAV_ITEMS == [
            ("home", "홈"),
            ("task_request", "작업 요청"),
            ("task_monitor", "작업 모니터"),
            ("alerts", "알림/로그"),
        ]
        assert window.admin_shell.has_page("home")
        assert window.admin_shell.has_page("task_request")
        assert window.admin_shell.has_page("task_monitor")
        assert window.admin_shell.has_page("alerts")
        assert type(window.request_page) is TaskRequestPage
        assert isinstance(window.monitor_page, PresentationTaskMonitorPage)
        assert isinstance(window.monitor_page, TaskMonitorPage)
        assert isinstance(window.alerts_page, PresentationAlertsLogPage)
        assert isinstance(window.alerts_page, AlertLogPage)
        assert not hasattr(window.request_page, "submit_demo_request")
        assert "추종" not in texts
        assert "좌표/구역 설정" not in texts
        assert "로봇 상태" not in texts
        assert "재고 관리" not in texts
        assert "어르신 정보" not in texts
        assert "ROPI 1" in texts
        assert "ROPI 2" in texts
        assert "ROPI 3" in texts
        assert "지원 기능" not in texts
        assert "현재 ROPI 위치와 진행 중인 업무를 맵 위에 표시합니다." not in texts
        assert "B동 복도" not in texts
        assert "303호 앞" not in texts
        assert {"복도1", "303호", "복도3"}.issubset(set(texts))
        assert any(
            frame.property("presentation_home_map") is True
            for frame in window.findChildren(QFrame)
        )
        assert not window.findChildren(QFrame, "homeMapFlowRow")
        assert not window.findChildren(QFrame, "homeOperationMapPanel")
        assert "맵을 불러오지 않았습니다." not in texts
        assert any(
            frame.property("presentation_compact_flow") is True
            for frame in window.findChildren(QFrame)
        )
        assert (
            window.home_page.presentation_map_card.minimumHeight()
            == window.home_page.compact_flow_card.minimumHeight()
        )
        assert (
            window.home_page.presentation_map_card.maximumHeight()
            == window.home_page.compact_flow_card.maximumHeight()
        )
        assert window.home_page.flow_scroll.parentWidget().isHidden()
        assert window.map_widget.marker_count == 3
        assert window.map_widget.route_hint_enabled is False
        assert window.map_widget.maximumWidth() <= 560
        assert window.map_widget.maximumHeight() <= 320
        assert window.map_widget.map_loaded is True
        assert window.map_widget.map_image_size is not None
        assert all(
            token not in lowered
            for token in ("pinky", "jetcobot", "arm1", "arm2")
        )
    finally:
        window.close()


def test_robot_display_adapter_maps_runtime_robot_names_recursively():
    from ui.presentation_demo.robot_display import (
        display_robot_name,
        runtime_robot_id_for_display,
        translate_robot_display_payload,
    )

    payload = {
        "assigned_robot_id": "pinky2",
        "latest_robot": {"robot_id": "pinky3"},
        "message": "pinky2 moved while arm1 and jetcobot2 are hidden",
        "task_type": "DELIVERY",
        "task_status": "RUNNING",
        "phase": "DELIVERY_DESTINATION",
        "event_type": "TASK_UPDATED",
        "reason_code": "PATROL_RUNTIME_NOT_READY",
        "workflow_event": "WORKFLOW_RESULT_RECORDED",
        "waiting_state": "WAITING_FMS_RESERVATION",
        "history_name": "TASK_STATE_HISTORY",
        "confirm_phase": "WAIT_GUIDE_START_CONFIRM",
        "mixed_status": "WAIT 안내 START CONFIRM",
        "events": [{"robot_id": "pinky1"}],
    }

    translated = translate_robot_display_payload(payload)

    assert display_robot_name("pinky1") == "ROPI 1"
    assert display_robot_name("pinky2") == "ROPI 2"
    assert display_robot_name("pinky3") == "ROPI 3"
    assert runtime_robot_id_for_display("ROPI 1") == "pinky1"
    assert runtime_robot_id_for_display("ROPI 2") == "pinky2"
    assert runtime_robot_id_for_display("ROPI 3") == "pinky3"
    assert translated["assigned_robot_id"] == "ROPI 2"
    assert translated["latest_robot"]["robot_id"] == "ROPI 3"
    assert translated["events"][0]["robot_id"] == "ROPI 1"
    assert translated["task_type"] == "운반"
    assert translated["task_status"] == "진행 중"
    assert translated["phase"] == "목적지 이동"
    assert translated["event_type"] == "작업 갱신"
    assert translated["reason_code"] == "순찰 실행 준비 안 됨"
    assert translated["workflow_event"] == "업무 흐름 결과 기록됨"
    assert translated["waiting_state"] == "FMS 예약 대기"
    assert translated["history_name"] == "작업 상태 이력"
    assert translated["confirm_phase"] == "안내 시작 확인 대기"
    assert translated["mixed_status"] == "대기 안내 시작 확인"
    assert "ROPI 2" in translated["message"]
    assert "운반 장치" in translated["message"]
    assert "pinky" not in str(translated).lower()
    assert "arm1" not in str(translated).lower()
    assert "jetcobot" not in str(translated).lower()
    assert payload["assigned_robot_id"] == "pinky2"


def test_demo_task_monitor_uses_db_page_with_ropi_display_mapping():
    _app()

    from ui.presentation_demo.admin_demo_app import PresentationTaskMonitorPage

    page = PresentationTaskMonitorPage(autostart_stream=False)

    try:
        page.apply_snapshot(
            {
                "tasks": [
                    {
                        "task_id": 1034,
                        "task_type": "DELIVERY",
                        "task_status": "RUNNING",
                        "phase": "DELIVERY_DESTINATION",
                        "assigned_robot_id": "pinky2",
                        "latest_robot": {"robot_id": "pinky2"},
                        "result_code": "REJECTED",
                        "latest_reason_code": "PATROL_RUNTIME_NOT_READY",
                        "result_message": "WORKFLOW_RESULT_RECORDED",
                        "feedback_summary": (
                            "WAITING_FMS_RESERVATION / WAIT_GUIDE_START_CONFIRM"
                        ),
                    }
                ]
            }
        )

        texts = _display_texts(page)
        text_blob = " ".join(texts)

        assert "ROPI 2" in texts
        assert "운반" in texts
        assert "진행 중" in texts
        assert "목적지 이동" in texts
        assert "거절" in texts
        assert "순찰 실행 준비 안 됨" in texts
        assert "업무 흐름 결과 기록됨" in text_blob
        assert "FMS 예약 대기" in text_blob
        assert "안내 시작 확인 대기" in text_blob
        assert "pinky2" not in text_blob.lower()
        assert "DELIVERY" not in text_blob
        assert "RUNNING" not in text_blob
        assert "DELIVERY_DESTINATION" not in text_blob
        assert "REJECTED" not in text_blob
        assert "PATROL_RUNTIME_NOT_READY" not in text_blob
        assert "WORKFLOW_RESULT_RECORDED" not in text_blob
        assert "WAITING_FMS_RESERVATION" not in text_blob
        assert "WAIT_GUIDE_START_CONFIRM" not in text_blob
        assert "START" not in text_blob
        assert "CONFIRM" not in text_blob
        assert page.task_table.columnWidth(4) <= 96
    finally:
        page.shutdown()
        page.close()


def test_demo_fall_evidence_dialog_uses_korean_presentation_labels():
    _app()

    from ui.presentation_demo.admin_demo_app import PresentationTaskMonitorPage

    page = PresentationTaskMonitorPage(autostart_stream=False)
    dialog = None
    empty_dialog = None

    try:
        dialog = page._create_fall_evidence_dialog(
            {
                "result_code": "OK",
                "evidence_image_id": "EVD-2001-44",
                "frame_id": "camera_frame",
                "image_width_px": 640,
                "image_height_px": 480,
                "detections": [
                    {"class_name": "fall", "confidence": 0.91},
                    {"class_name": "person", "confidence": 0.77},
                ],
            }
        )
        texts = _display_texts(dialog)
        text_blob = " ".join(texts)

        assert "증거사진 번호" in texts
        assert "좌표계" in texts
        assert "낙상 0.91" in text_blob
        assert "사람 0.77" in text_blob
        assert "evidence_image_id" not in text_blob
        assert "frame_id" not in text_blob
        assert "fall 0.91" not in text_blob
        assert "person 0.77" not in text_blob

        empty_dialog = page._create_fall_evidence_dialog(
            {
                "result_code": "OK",
                "evidence_image_id": "EVD-2001-45",
                "frame_id": "camera_frame",
                "detections": [],
            }
        )
        empty_text_blob = " ".join(_display_texts(empty_dialog))
        assert "감지 영역 없음" in empty_text_blob
        assert "bbox" not in empty_text_blob
    finally:
        if dialog is not None:
            dialog.close()
        if empty_dialog is not None:
            empty_dialog.close()
        page.shutdown()
        page.close()


def test_demo_alert_logs_uses_db_page_with_ropi_display_mapping():
    _app()

    from ui.presentation_demo.admin_demo_app import PresentationAlertsLogPage

    page = PresentationAlertsLogPage(autoload=False)

    try:
        assert page.robot_id_input.placeholderText() == "예: ROPI 2"
        page.robot_id_input.setText("ROPI 3")
        assert page._collect_filters()["robot_id"] == "pinky3"

        page.apply_alert_log_bundle(
            {
                "summary": {
                    "total_event_count": 1,
                    "warning_count": 0,
                    "error_count": 0,
                    "critical_count": 0,
                },
                "events": [
                    {
                        "event_id": 2001,
                        "occurred_at": "2026-05-12T14:35:00",
                        "severity": "INFO",
                        "source_component": "Control Service",
                        "task_id": 1034,
                        "robot_id": "pinky3",
                        "event_type": "TASK_UPDATED",
                        "message": "pinky3 PATROL RUNNING update",
                        "result_code": "ACCEPTED",
                        "reason_code": "PATROL_RUNTIME_NOT_READY",
                        "payload": {
                            "assigned_robot_id": "pinky3",
                            "task_status": "RUNNING",
                            "phase": "PATROL_RUNNING",
                            "workflow_event": "WORKFLOW_RESULT_RECORDED",
                            "waiting_state": "WAITING_FMS_RESERVATION",
                            "task_history": "TASK_STATE_HISTORY",
                            "guide_confirm": "WAIT 안내 START CONFIRM",
                            "arm_id": "arm1",
                        },
                    }
                ],
            }
        )

        texts = _display_texts(page)
        text_blob = " ".join(texts)

        assert "ROPI 3" in texts
        assert "정보" in texts
        assert "작업 갱신" in texts
        assert "접수" in texts
        assert "순찰 실행 준비 안 됨" in texts
        assert "담당 ROPI" in text_blob
        assert "진행 중" in text_blob
        assert "순찰 중" in text_blob
        assert "업무 흐름" in text_blob
        assert "FMS 예약 대기" in text_blob
        assert "작업 상태 이력" in text_blob
        assert "대기 안내 시작 확인" in text_blob
        assert "pinky3" not in text_blob.lower()
        assert "arm1" not in text_blob.lower()
        assert "운반 장치" in text_blob
        assert "TASK_UPDATED" not in text_blob
        assert "PATROL_RUNTIME_NOT_READY" not in text_blob
        assert "assigned_robot_id" not in text_blob
        assert "task_status" not in text_blob
        assert "phase" not in text_blob
        assert "WORKFLOW_RESULT_RECORDED" not in text_blob
        assert "WAITING_FMS_RESERVATION" not in text_blob
        assert "TASK_STATE_HISTORY" not in text_blob
        assert "WAIT" not in text_blob
        assert "START" not in text_blob
        assert "CONFIRM" not in text_blob
    finally:
        page.shutdown()
        page.close()


def test_admin_demo_smoke_mode_returns_without_event_loop():
    _app()

    from ui.presentation_demo import admin_demo_app

    admin_demo_app.main(["--smoke"])


def test_admin_demo_window_opens_maximized():
    _app()

    from ui.presentation_demo.admin_demo_app import (
        create_demo_window,
        show_demo_window,
    )

    window = create_demo_window(autostart_runtime=False)

    try:
        show_demo_window(window)

        assert window.windowState() & Qt.WindowState.WindowMaximized
        assert window.maximumWidth() > 2000
        assert window.maximumHeight() > 1200
    finally:
        window.close()


def test_admin_demo_has_page_neutral_uv_script_and_tracked_source():
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    scripts = pyproject["project"]["scripts"]

    assert scripts["ropi-admin-demo"] == "ui.presentation_demo.admin_demo_app:main"
    assert "ropi-admin-home-demo" not in scripts

    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "ui/presentation_demo/exports/" in gitignore
    assert "ui/presentation_demo/\n" not in gitignore
    assert "test/unit/ui/test_presentation_admin_demo.py" not in gitignore
