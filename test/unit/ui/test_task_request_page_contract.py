import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QComboBox,
    QFrame,
    QGridLayout,
    QTextEdit,
)

from ui.utils.session.session_manager import SessionManager, UserSession


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def test_task_request_page_uses_logger_instead_of_direct_print():
    source_path = (
        Path(__file__).resolve().parents[3]
        / "ui"
        / "utils"
        / "pages"
        / "caregiver"
        / "task_request_page.py"
    )
    source = source_path.read_text(encoding="utf-8")

    assert "logger = logging.getLogger(__name__)" in source
    assert "print(" not in source


def test_task_request_page_exposes_delivery_patrol_and_disabled_follow_tabs(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_request_page import (
        DeliveryRequestForm,
        TaskRequestPage,
    )

    monkeypatch.setattr(DeliveryRequestForm, "ensure_items_loaded", lambda self: None)

    page = TaskRequestPage()

    try:
        tabs = [
            button.text()
            for button in page.findChildren(QPushButton)
            if button.objectName() == "scenarioTabButton"
        ]
        assert tabs == [
            "물품 운반",
            "순찰",
            "추종",
        ]
        assert all("준비 중" not in text for text in tabs)

        assert page.delivery_form.submit_btn.isEnabled() is True
        page.patrol_btn.click()
        assert page.current_form is page.patrol_form
        assert page.patrol_form.submit_btn.isEnabled() is False
        assert page.patrol_form.submit_btn.text() == "순찰 요청 등록"

        assert not hasattr(page, "guide_btn")
        assert not hasattr(page, "guide_form")
        assert page.follow_btn.isEnabled() is False
        assert not hasattr(page, "follow_form")
        page.follow_btn.click()
        assert page.current_form is page.patrol_form
    finally:
        page.close()


def test_delivery_request_preview_uses_standard_fields_and_no_task_id_before_submit(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_request_page import (
        DeliveryRequestForm,
        TaskRequestPage,
    )

    monkeypatch.setattr(DeliveryRequestForm, "ensure_items_loaded", lambda self: None)
    SessionManager.login(UserSession(user_id="7", name="김보호", role="caregiver"))

    page = TaskRequestPage()

    try:
        page.delivery_form.item_combo.addItem(
            "세면도구 세트 / 재고 4개",
            {"item_id": 1, "item_name": "세면도구 세트", "quantity": 4},
        )
        page.delivery_form.destination_combo.clear()
        page.delivery_form.destination_combo.addItem("301호", "delivery_room_301")
        page.delivery_form.quantity_input.setValue(2)
        page.delivery_form.destination_combo.setCurrentIndex(0)
        page.delivery_form.set_priority("URGENT")
        page.delivery_form.emit_preview_changed()

        assert page.preview_caregiver_id.text() == "7"
        assert page.preview_item.text() == "세면도구 세트"
        assert page.preview_quantity.text() == "2개"
        assert page.preview_destination.text() == "delivery_room_301"
        assert page.preview_priority.text() == "긴급"
        assert page.preview_priority.objectName() == "priorityChip"
        assert all("task_id" not in text.lower() for text in _label_texts(page.preview_card))
    finally:
        SessionManager.logout()
        page.close()


def test_task_request_page_uses_content_height_form_card_and_robot_placeholder(monkeypatch):
    app = _app()

    from ui.utils.pages.caregiver.task_request_page import (
        DeliveryRequestForm,
        TaskRequestPage,
    )

    monkeypatch.setattr(DeliveryRequestForm, "ensure_items_loaded", lambda self: None)

    page = TaskRequestPage()

    try:
        page.delivery_form.destination_combo.clear()
        page.delivery_form.destination_combo.addItem("301호", "delivery_room_301")
        page.delivery_form.emit_preview_changed()
        page.resize(1200, 800)
        page.show()
        app.processEvents()

        form = page.delivery_form
        blank_below_submit = form.height() - form.submit_btn.geometry().bottom() - 1

        assert blank_below_submit <= 16
        assert form.height() <= form.sizeHint().height() + 12
        assert page.form_scroll.height() <= form.sizeHint().height() + 12
        assert page.left_card.height() <= page.form_scroll.height() + 60
        assert page.time_card.objectName() == "pageTimeCard"
        assert page.form_scroll.objectName() == "requestFormScroll"
        assert page.side_scroll.objectName() == "requestSideScroll"

        assert page.robot_status_card.objectName() == "robotStatusCard"
        assert page.robot_map_placeholder.objectName() == "robotMapPlaceholder"
        assert "전송 전 payload 기준 필드를 확인합니다." not in _label_texts(page.preview_card)
        assert "작업 생성 후 로봇 feedback 수신 시 위치와 상태를 갱신합니다." not in _label_texts(page.robot_status_card)
        assert "서버가 반환한 IF-DEL-001 응답 필드를 그대로 표시합니다." not in _label_texts(page.result_card)
        assert page.robot_id_label.text() == "pinky2"
        assert page.robot_state_label.text() == "feedback 수신 전"
        assert page.robot_state_label.objectName() == "robotStateChip"
        assert page.robot_pose_label.text() == "미수신"
        assert page.robot_destination_label.text() == "delivery_room_301"
        metric_rows = page.side_panel.findChildren(QFrame, "sideMetricRow")
        assert len(metric_rows) >= 14
        assert page.side_scroll.widget() is page.side_panel
        assert page.side_scroll.height() < page.side_panel.height()
    finally:
        page.close()


def test_patrol_request_tab_uses_pat_001_fields_and_preview(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_request_page import (
        DeliveryRequestForm,
        TaskRequestPage,
    )

    monkeypatch.setattr(DeliveryRequestForm, "ensure_items_loaded", lambda self: None)
    SessionManager.login(UserSession(user_id="7", name="김보호", role="caregiver"))

    page = TaskRequestPage()

    try:
        page.patrol_form.set_patrol_areas(
            [
                {
                    "patrol_area_id": "patrol_ward_night_01",
                    "patrol_area_name": "야간 병동 순찰",
                    "patrol_area_revision": 7,
                    "map_id": "map_test11_0423",
                    "waypoint_count": 3,
                    "path_frame_id": "map",
                    "active": True,
                }
            ]
        )
        page.patrol_btn.click()

        form = page.patrol_form
        assert form.submit_btn.isEnabled() is True
        assert form.submit_btn.text() == "순찰 요청 등록"
        assert form.findChild(QGridLayout, "patrolFormGrid") is not None
        assert form.patrol_area_combo.isEditable() is True
        assert form.patrol_area_combo.completer() is not None

        area_combo = form.findChild(QComboBox, "patrolAreaCombo")
        assert area_combo is form.patrol_area_combo

        priority_buttons = [
            button.text()
            for button in form.findChildren(QPushButton)
            if button.objectName() == "prioritySegmentButton"
        ]
        assert priority_buttons == ["일반", "긴급", "최우선"]

        form.set_priority("URGENT")
        form.emit_preview_changed()

        assert page.preview_caregiver_id.text() == "7"
        assert page.preview_item.text() == "야간 병동 순찰"
        assert page.preview_quantity.text() == "patrol_ward_night_01"
        assert page.preview_destination.text() == "작업 생성 후 확정"
        assert page.preview_priority.text() == "긴급"
        assert page.robot_id_label.text() == "미정"
        assert page.robot_state_label.text() == "feedback 수신 전"
        assert page.robot_pose_label.text() == "미수신"
        assert page.robot_destination_label.text() == "미수신"
        assert page.robot_map_label.text() == "순찰 요청 미리보기"
        assert form.findChild(QFrame, "patrolRouteSummaryCard") is None
        assert not hasattr(form, "map_id_label")
        assert not hasattr(form, "waypoint_count_label")
        assert not hasattr(form, "path_frame_id_label")

        payload = form._build_create_patrol_task_payload(SessionManager.current_user())
        assert payload["caregiver_id"] == 7
        assert payload["patrol_area_id"] == "patrol_ward_night_01"
        assert payload["priority"] == "URGENT"
        assert "notes" not in payload
        assert payload["request_id"].startswith("req_patrol_")
        assert payload["idempotency_key"].startswith("idem_patrol_")

        notes = form.findChild(QTextEdit, "patrolNotesInput")
        assert notes is form.notes_input
        assert notes.maximumHeight() <= 88
    finally:
        SessionManager.logout()
        page.close()


def test_delivery_form_uses_wireframe_form_controls():
    app = _app()

    from ui.utils.pages.caregiver.task_request_page import DeliveryRequestForm

    form = DeliveryRequestForm()

    try:
        assert form.findChild(QGridLayout, "deliveryFormGrid") is not None
        assert form.item_combo.isEditable() is True
        assert form.item_combo.completer() is not None
        assert form.item_combo.lineEdit().placeholderText() == "물품명 검색"
        assert form.destination_combo.isEditable() is True
        assert form.destination_combo.completer() is not None

        priority_buttons = [
            button.text()
            for button in form.findChildren(QPushButton)
            if button.objectName() == "prioritySegmentButton"
        ]
        assert priority_buttons == ["일반", "긴급", "최우선"]
        assert list(form.priority_buttons.keys()) == ["NORMAL", "URGENT", "HIGHEST"]
        assert form.get_priority_code() == "NORMAL"

        form.set_priority("URGENT")
        assert form.get_priority_code() == "URGENT"
        assert form.priority_buttons["URGENT"].isChecked() is True
        assert form.priority_buttons["URGENT"].text() == "긴급"

        notes = form.findChild(QTextEdit, "deliveryNotesInput")
        assert notes is form.detail_input
        assert notes.minimumHeight() <= 88
        assert notes.maximumHeight() <= 88

        grid = form.findChild(QGridLayout, "deliveryFormGrid")
        assert grid.verticalSpacing() <= 6

        notes_group = form.findChild(QFrame, "notesFieldGroup")
        assert notes_group is not None
        assert notes_group.layout().spacing() <= 2

        form.resize(520, 760)
        form.show()
        app.processEvents()

        priority_group = form.priority_segment.parentWidget()
        notes_label = notes_group.findChild(QLabel)
        title_label = form.findChild(QLabel, "sectionTitle")
        rendered_gap = (
            notes_group.geometry().top()
            - priority_group.geometry().bottom()
            - 1
        )
        assert rendered_gap <= 8
        assert notes_group.height() <= 120
        assert notes_label.height() <= 24
        assert title_label.height() <= 32
        assert grid.geometry().top() <= 56
    finally:
        form.close()


def test_delivery_items_load_failure_allows_retry(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_request_page import DeliveryRequestForm

    form = DeliveryRequestForm()
    load_calls = []

    def fake_load_items():
        load_calls.append("load")
        form.load_thread = None

    monkeypatch.setattr(form, "_load_items", fake_load_items)

    try:
        assert form.items_load_state == "idle"

        form.ensure_items_loaded()
        assert load_calls == ["load"]
        assert form.items_load_state == "loading"

        form._handle_items_loaded(False, "server down")
        assert form.items_load_state == "failed"

        form.ensure_items_loaded()
        assert load_calls == ["load", "load"]
        assert form.items_load_state == "loading"
    finally:
        form.close()


def test_delivery_form_loads_items_and_destinations_from_server_options():
    _app()

    from ui.utils.pages.caregiver.task_request_page import DeliveryRequestForm

    form = DeliveryRequestForm()
    emitted_options = []
    form.options_loaded.connect(emitted_options.append)

    try:
        assert not hasattr(DeliveryRequestForm, "DESTINATION_OPTIONS")

        form._handle_items_loaded(
            True,
            {
                "items": [
                    {"item_id": 1, "item_name": "세면도구 세트", "quantity": 4}
                ],
                "destinations": [
                    {
                        "destination_id": "delivery_room_301",
                        "display_name": "301호",
                    }
                ],
                "patrol_areas": [
                    {
                        "patrol_area_id": "patrol_ward_night_01",
                        "patrol_area_name": "야간 병동 순찰",
                        "patrol_area_revision": 7,
                        "map_id": "map_test11_0423",
                        "waypoint_count": 3,
                    }
                ],
            },
        )

        assert form.item_combo.currentData()["item_id"] == 1
        assert form.item_combo.currentText() == "세면도구 세트 / 재고 4개"
        assert form.destination_combo.currentText() == "301호"
        assert form.destination_combo.currentData() == "delivery_room_301"
        assert emitted_options[0]["patrol_areas"][0]["patrol_area_id"] == (
            "patrol_ward_night_01"
        )
    finally:
        form.close()


def test_patrol_form_loads_area_options_from_server_options():
    _app()

    from ui.utils.pages.caregiver.task_request_page import PatrolRequestForm

    form = PatrolRequestForm()

    try:
        assert not hasattr(PatrolRequestForm, "PATROL_AREA_OPTIONS")

        form.set_patrol_areas(
            [
                {
                    "patrol_area_id": "patrol_ward_night_01",
                    "patrol_area_name": "야간 병동 순찰",
                    "patrol_area_revision": 7,
                    "map_id": "map_test11_0423",
                    "waypoint_count": 3,
                    "path_frame_id": "map",
                    "active": True,
                }
            ]
        )

        assert form.patrol_area_combo.currentText() == "야간 병동 순찰 (rev 7, 활성)"
        assert form.patrol_area_combo.currentData()["patrol_area_id"] == (
            "patrol_ward_night_01"
        )
        assert form.findChild(QFrame, "patrolRouteSummaryCard") is None
        assert not hasattr(form, "map_id_label")
        assert not hasattr(form, "waypoint_count_label")
        assert not hasattr(form, "path_frame_id_label")

        form.set_patrol_areas(
            [
                {
                    "patrol_area_id": "patrol_no_robot",
                    "patrol_area_name": "로봇 미정 순찰",
                    "patrol_area_revision": 1,
                    "map_id": "map_test11_0423",
                    "waypoint_count": 0,
                    "path_frame_id": "map",
                    "active": True,
                }
            ]
        )
        assert form.patrol_area_combo.currentData()["patrol_area_id"] == (
            "patrol_no_robot"
        )
    finally:
        form.close()


class _FakeThread:
    def __init__(self):
        self.quit_count = 0
        self.wait_count = 0
        self.wait_timeout = None
        self._running = True

    def isRunning(self):
        return self._running

    def quit(self):
        self.quit_count += 1
        self._running = False

    def wait(self, timeout_ms):
        self.wait_count += 1
        self.wait_timeout = timeout_ms
        return True


def test_delivery_form_close_stops_running_worker_threads():
    app = _app()

    from ui.utils.pages.caregiver.task_request_page import DeliveryRequestForm

    form = DeliveryRequestForm()
    load_thread = _FakeThread()
    submit_thread = _FakeThread()
    form.load_thread = load_thread
    form.load_worker = object()
    form.submit_thread = submit_thread
    form.submit_worker = object()

    form.show()
    app.processEvents()
    form.close()
    app.processEvents()

    assert load_thread.quit_count == 1
    assert load_thread.wait_count == 1
    assert submit_thread.quit_count == 1
    assert submit_thread.wait_count == 1
    assert form.load_thread is None
    assert form.load_worker is None
    assert form.submit_thread is None
    assert form.submit_worker is None


def test_delivery_submit_result_panel_displays_if_del_001_response_fields(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_request_page import (
        DeliveryRequestForm,
        TaskRequestPage,
    )

    monkeypatch.setattr(DeliveryRequestForm, "ensure_items_loaded", lambda self: None)

    page = TaskRequestPage()
    page.delivery_form.refresh_data = lambda: None

    try:
        page.delivery_form._handle_submit_finished(
            True,
            {
                "result_code": "ACCEPTED",
                "result_message": "작업이 접수되었습니다.",
                "reason_code": None,
                "task_id": 1001,
                "task_status": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky2",
            },
        )

        assert page.result_code_label.text() == "ACCEPTED"
        assert page.result_message_label.text() == "작업이 접수되었습니다."
        assert page.reason_code_label.text() == "-"
        assert page.task_id_label.text() == "1001"
        assert page.task_status_label.text() == "WAITING_DISPATCH"
        assert page.assigned_robot_id_label.text() == "pinky2"

        page.delivery_form._handle_submit_finished(
            False,
            {
                "result_code": "REJECTED",
                "result_message": "재고가 부족합니다.",
                "reason_code": "ITEM_QUANTITY_INSUFFICIENT",
                "task_id": None,
                "task_status": None,
                "assigned_robot_id": None,
            },
        )

        assert page.result_code_label.text() == "REJECTED"
        assert page.result_message_label.text() == "재고가 부족합니다."
        assert page.reason_code_label.text() == "ITEM_QUANTITY_INSUFFICIENT"
        labels = _label_texts(page)
        assert all("assigned_pinky_id" not in text for text in labels)
    finally:
        page.close()


def test_task_request_page_cancel_button_updates_result_panel(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_request_page import (
        DeliveryRequestForm,
        TaskRequestPage,
    )

    monkeypatch.setattr(DeliveryRequestForm, "ensure_items_loaded", lambda self: None)

    page = TaskRequestPage()
    page.delivery_form.refresh_data = lambda: None
    requested_task_ids = []

    monkeypatch.setattr(page, "_confirm_cancel_task", lambda task_id: True)
    monkeypatch.setattr(
        page,
        "_start_cancel_delivery_task",
        lambda task_id: requested_task_ids.append(task_id),
    )

    try:
        page.delivery_form._handle_submit_finished(
            True,
            {
                "result_code": "ACCEPTED",
                "result_message": "작업이 접수되었습니다.",
                "reason_code": None,
                "task_id": 1001,
                "task_status": "WAITING_DISPATCH",
                "assigned_robot_id": "pinky2",
                "cancellable": True,
            },
        )

        assert page.cancel_task_btn.isEnabled() is True

        page.cancel_task_btn.click()

        assert requested_task_ids == [1001]
        assert page.cancel_task_btn.isEnabled() is False
        assert page.cancel_task_btn.text() == "취소 요청 전송 중..."

        page._handle_cancel_finished(
            True,
            {
                "result_code": "CANCEL_REQUESTED",
                "result_message": "취소 요청이 접수되었습니다.",
                "reason_code": "USER_CANCEL_REQUESTED",
                "task_id": 1001,
                "task_status": "CANCEL_REQUESTED",
                "assigned_robot_id": "pinky2",
                "cancel_requested": True,
            },
        )

        assert page.result_code_label.text() == "CANCEL_REQUESTED"
        assert page.result_message_label.text() == "취소 요청이 접수되었습니다."
        assert page.reason_code_label.text() == "USER_CANCEL_REQUESTED"
        assert page.task_status_label.text() == "CANCEL_REQUESTED"
        assert page.cancel_task_btn.isEnabled() is False
        assert page.cancel_task_btn.text() == "취소 처리 중"
    finally:
        page.close()


def test_task_request_page_does_not_embed_patrol_resume_form(monkeypatch):
    _app()

    from ui.utils.pages.caregiver.task_request_page import (
        DeliveryRequestForm,
        TaskRequestPage,
    )

    monkeypatch.setattr(DeliveryRequestForm, "ensure_items_loaded", lambda self: None)

    page = TaskRequestPage()

    try:
        page.side_panel.show_delivery_result(
            {
                "result_code": "TASK_UPDATED",
                "task_id": "2001",
                "task_type": "PATROL",
                "task_status": "RUNNING",
                "phase": "WAIT_FALL_RESPONSE",
                "assigned_robot_id": "pinky3",
                "cancellable": True,
            }
        )

        assert page.findChild(QFrame, "patrolResumeActionPanel") is None
        assert not hasattr(page.side_panel, "patrol_resume_btn")
        assert not hasattr(page, "_request_patrol_resume")
    finally:
        page.close()


def test_delivery_create_payload_uses_numeric_ui_api_ids():
    _app()

    from ui.utils.pages.caregiver.task_request_page import DeliveryRequestForm

    SessionManager.login(UserSession(user_id="7", name="김보호", role="caregiver"))
    form = DeliveryRequestForm()

    try:
        form.item_combo.addItem(
            "세면도구 세트 / 재고 4개",
            {"item_id": "1", "item_name": "세면도구 세트", "quantity": 4},
        )
        form.destination_combo.clear()
        form.destination_combo.addItem("301호", "delivery_room_301")
        form.set_priority("URGENT")
        payload = form._build_create_delivery_task_payload(SessionManager.current_user())

        assert payload["caregiver_id"] == 7
        assert payload["item_id"] == 1
        assert payload["quantity"] == 1
        assert payload["destination_id"] == "delivery_room_301"
        assert payload["priority"] == "URGENT"
        assert "assigned_pinky_id" not in payload
    finally:
        SessionManager.logout()
        form.close()
