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
        DEMO_MAP_CANVAS_SIZE,
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
        assert not isinstance(window.monitor_page, TaskMonitorPage)
        assert isinstance(window.alerts_page, PresentationAlertsLogPage)
        assert isinstance(window.alerts_page, AlertLogPage)
        assert window.alerts_page.table.rowCount() == 5
        assert window.alerts_page.table.item(0, 0).text() == "EV-20260513-014"
        assert window.alerts_page.table.item(0, 5).text() == "ROPI 3"
        assert window.alerts_page.table.item(0, 6).text() == "낙상 의심 감지"
        assert window.alerts_page.related_task_button.isEnabled()
        assert window.alerts_page.related_robot_button.isEnabled()
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
        assert window.home_page.presentation_map_flow_row is not None
        row_layout = window.home_page.presentation_map_flow_row.layout()
        assert row_layout.stretch(0) == 1
        assert row_layout.stretch(1) == 1
        assert (
            window.home_page.presentation_map_card.maximumWidth()
            == window.home_page.compact_flow_card.maximumWidth()
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
        assert DEMO_MAP_CANVAS_SIZE[0] >= 590
        assert DEMO_MAP_CANVAS_SIZE[1] >= 330
        assert window.map_widget.maximumWidth() == DEMO_MAP_CANVAS_SIZE[0]
        assert window.map_widget.maximumHeight() == DEMO_MAP_CANVAS_SIZE[1]
        assert window.map_widget.map_loaded is True
        assert window.map_widget.map_image_size is not None
        image_width, image_height = window.map_widget.map_image_size
        canvas_ratio = DEMO_MAP_CANVAS_SIZE[0] / DEMO_MAP_CANVAS_SIZE[1]
        image_ratio = image_width / image_height
        assert abs(canvas_ratio - image_ratio) < 0.01
        home_style = window.home_page.styleSheet()
        assert "QLabel#homeRobotFieldValue" in home_style
        assert "QLabel#homeTaskTitle" in home_style
        assert "font-size: 16px" in home_style
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


def test_demo_task_monitor_uses_slide_capture_fixture_without_runtime():
    _app()

    from ui.presentation_demo.admin_demo_app import PresentationTaskMonitorPage
    from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

    page = PresentationTaskMonitorPage()

    try:
        assert not isinstance(page, TaskMonitorPage)
        assert not hasattr(page, "consumer_id")
        assert page.selected_task_id == "#1024"
        assert page.task_table.rowCount() == 4
        assert page.task_table.item(0, 1).text() == "의료키트 운반"
        assert page.task_table.item(1, 2).text() == "순찰"
        assert page.task_table.item(2, 2).text() == "안내"
        assert page.task_table.item(3, 0).text() == "완료"

        texts = _display_texts(page)
        text_blob = " ".join(texts)

        assert "의료키트 운반 #1024" in texts
        assert "목적지 도착 / 전달 대기" in texts
        assert "303호 앞 도착, 전달 대기 중" in texts
        assert {"작업 목록", "현재 단계", "최근 피드백"}.issubset(set(texts))
        assert {"운반", "순찰", "안내"}.issubset(set(texts))
        assert "진행 중" in texts
        assert "주의 필요" in texts
        assert "완료" in texts
        assert "ROPI 1" in texts
        assert "ROPI 2" in texts
        assert "ROPI 3" in texts
        assert "요청 접수" in text_blob
        assert "픽업 이동" in text_blob
        assert "적재 완료" in text_blob
        assert "목적지 이동" in text_blob
        assert "전달 대기" in text_blob
        assert not any(
            frame.property("presentation_callout") is True
            for frame in page.findChildren(QFrame)
        )
        assert "운반/순찰/안내를 같은 task 단위로 추적" not in text_blob
        assert "단계와 최근 피드백으로 진행 위치 확인" not in text_blob
        assert "로봇 주행 결과가 UI에 반영됨" not in text_blob
        assert "snapshot 이후" not in text_blob
        assert "TASK_UPDATED" not in text_blob
        assert "ACTION_FEEDBACK_UPDATED" not in text_blob
        assert "pinky2" not in text_blob.lower()
        assert "jetcobot" not in text_blob.lower()
        assert "arm1" not in text_blob.lower()
        assert "DELIVERY" not in text_blob
        assert "DELIVERY_DESTINATION" not in text_blob
    finally:
        page.close()


def test_demo_task_monitor_replays_delivery_lifecycle_when_task_clicked():
    _app()

    from ui.presentation_demo.admin_demo_app import PresentationTaskMonitorPage

    page = PresentationTaskMonitorPage()

    try:
        assert page.progress_timer.interval() == 1000
        assert page.current_step_index == 4
        assert page.step_current_labels[4].text() == "현재"

        page.task_table.cellClicked.emit(0, 1)

        assert page.progress_timer.isActive()
        assert page.selected_task_id == "#1024"
        assert page.current_step_index == 0
        assert page.step_current_labels[0].text() == "현재"
        assert page.task_table.item(0, 4).text() == "요청 접수"
        assert page.task_table.item(0, 5).text() == "14:24"

        for expected_index, (expected_step, expected_time) in enumerate(
            (
                ("픽업 이동", "14:25"),
                ("적재 완료", "14:26"),
                ("목적지 이동", "14:27"),
                ("전달 대기", "14:28"),
                ("완료", "14:29"),
            ),
            start=1,
        ):
            page._advance_delivery_progress_animation()
            assert page.current_step_index == expected_index
            assert page.step_current_labels[expected_index].text() == "현재"
            assert page.task_table.item(0, 4).text() == expected_step
            assert page.task_table.item(0, 5).text() == expected_time

        assert not page.progress_timer.isActive()
        assert page.task_table.item(0, 0).text() == "완료"
    finally:
        page.close()


def test_demo_task_monitor_updates_non_delivery_rows_sparsely_during_replay():
    _app()

    from ui.presentation_demo.admin_demo_app import PresentationTaskMonitorPage

    page = PresentationTaskMonitorPage()

    def row_state(row_index: int) -> tuple[str, str]:
        return (
            page.task_table.item(row_index, 4).text(),
            page.task_table.item(row_index, 5).text(),
        )

    try:
        histories = {row_index: [] for row_index in range(page.task_table.rowCount())}
        changed_non_delivery_counts = []

        page.task_table.cellClicked.emit(0, 1)
        for row_index in histories:
            histories[row_index].append(row_state(row_index))

        while page.progress_timer.isActive():
            before = {
                row_index: row_state(row_index)
                for row_index in range(1, page.task_table.rowCount())
            }
            page._advance_delivery_progress_animation()
            for row_index in histories:
                histories[row_index].append(row_state(row_index))
            changed_non_delivery_counts.append(
                sum(
                    1
                    for row_index, previous in before.items()
                    if row_state(row_index) != previous
                )
            )

        delivery_phases = [phase for phase, _time in histories[0]]
        delivery_times = [update_time for _phase, update_time in histories[0]]
        assert len(set(delivery_phases)) == len(page.snapshot.lifecycle_steps)
        assert len(set(delivery_times)) == len(page.snapshot.lifecycle_steps)

        assert max(changed_non_delivery_counts) <= 2
        assert changed_non_delivery_counts.count(0) >= 2
        assert sum(changed_non_delivery_counts) <= 4
        assert sum(changed_non_delivery_counts) >= 2

        for row_index in range(1, page.task_table.rowCount()):
            phases = [phase for phase, _time in histories[row_index]]
            update_times = [update_time for _phase, update_time in histories[row_index]]
            assert len(set(phases)) <= 2, (row_index, phases)
            assert len(set(update_times)) <= 2, (row_index, update_times)
    finally:
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


def test_demo_alert_logs_capture_bundle_renders_operational_page_without_runtime():
    _app()

    from ui.presentation_demo.admin_demo_app import PresentationAlertsLogPage

    page = PresentationAlertsLogPage(autoload=False)

    try:
        texts = _display_texts(page)
        text_blob = " ".join(texts)
        normalized_text = text_blob.replace("\n", " ")
        lowered = normalized_text.lower()

        assert page.table.rowCount() == 5
        assert page.table.item(0, 0).text() == "EV-20260513-014"
        assert page.table.item(0, 2).text() == "주의"
        assert page.table.item(0, 4).text() == "#1033"
        assert page.table.item(0, 5).text() == "ROPI 3"
        assert page.table.item(0, 6).text() == "낙상 의심 감지"
        assert "복도3에서 낙상 의심 이벤트가 감지되었습니다." in text_blob

        assert {"전체 이벤트", "주의", "오류", "긴급"}.issubset(set(texts))
        assert {"12건", "2건", "1건", "0건"}.issubset(set(texts))
        assert {
            "낙상 의심 감지",
            "운반 목적지 도착",
            "안내 주행 시작",
            "작업 실행 준비 실패",
            "작업 완료",
        }.issubset(set(texts))
        assert "상세 내용" in normalized_text
        assert "확인 필요 사유" in texts
        assert "감지 신뢰도 0.91" in text_blob
        assert "감지 위치 복도3" in text_blob
        assert "관련 작업에서 낙상 증거 사진 확인 가능" in text_blob
        assert page.related_task_button.isEnabled()
        assert page.related_task_button.property("task_id") == "#1033"
        assert page.related_robot_button.isEnabled()
        assert page.related_robot_button.property("robot_id") == "ROPI 3"

        assert "작업 모니터에서 보기" in texts
        assert "로봇 상태에서 보기" in texts
        assert "낙상 사진 보기" not in text_blob
        assert "순찰 재개" not in text_blob
        assert "조치 완료" not in text_blob
        assert all(
            token not in lowered
            for token in (
                "demo",
                "presentation",
                "slide",
                "snapshot",
                "fixture",
                "capture",
                "ppt",
                "callout",
                "pinky",
                "jetcobot",
                "arm1",
                "arm2",
            )
        )
        assert "payload" not in lowered
        assert "reason_code" not in lowered
        assert "FALL_ALERT_CREATED" not in text_blob
        assert "WARNING" not in text_blob
        assert "TASK_FAILED" not in text_blob
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
        assert window.fullscreen_shortcut.key().toString() == "F11"

        window.toggle_fullscreen()
        assert window.windowState() & Qt.WindowState.WindowFullScreen

        window.toggle_fullscreen()
        assert window.windowState() & Qt.WindowState.WindowMaximized
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
