import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
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


def test_task_request_page_exposes_scenario_tabs_and_preparation_states(monkeypatch):
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
            "순찰 (준비 중)",
            "안내 (준비 중)",
            "추종 (준비 중)",
        ]

        assert page.delivery_form.submit_btn.isEnabled() is True

        for button, form in [
            (page.patrol_btn, page.patrol_form),
            (page.guide_btn, page.guide_form),
            (page.follow_btn, page.follow_form),
        ]:
            button.click()
            assert page.current_form is form
            assert form.submit_btn.isEnabled() is False
            assert "서버 workflow 연동 전" in form.not_ready_label.text()
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
            "세면도구 세트 (재고 4)",
            {"item_id": 1, "item_name": "세면도구 세트", "quantity": 4},
        )
        page.delivery_form.quantity_input.setValue(2)
        page.delivery_form.destination_combo.setCurrentIndex(0)
        page.delivery_form.set_priority("URGENT")
        page.delivery_form.emit_preview_changed()

        assert page.preview_caregiver_id.text() == "7"
        assert page.preview_item.text() == "세면도구 세트 (item_id: 1)"
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
        page.resize(1200, 800)
        page.show()
        app.processEvents()

        form = page.delivery_form
        blank_below_submit = form.height() - form.submit_btn.geometry().bottom() - 1

        assert blank_below_submit <= 16
        assert form.height() <= form.sizeHint().height() + 12
        assert page.form_scroll.height() <= form.sizeHint().height() + 12
        assert page.left_card.height() <= page.form_scroll.height() + 60

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


def test_delivery_form_uses_wireframe_form_controls():
    app = _app()

    from ui.utils.pages.caregiver.task_request_page import DeliveryRequestForm

    form = DeliveryRequestForm()

    try:
        assert form.findChild(QGridLayout, "deliveryFormGrid") is not None
        assert form.item_combo.isEditable() is True
        assert form.item_combo.completer() is not None
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


def test_delivery_create_payload_uses_numeric_ui_api_ids():
    _app()

    from ui.utils.pages.caregiver.task_request_page import DeliveryRequestForm

    SessionManager.login(UserSession(user_id="7", name="김보호", role="caregiver"))
    form = DeliveryRequestForm()

    try:
        form.item_combo.addItem(
            "세면도구 세트 (재고 4)",
            {"item_id": "1", "item_name": "세면도구 세트", "quantity": 4},
        )
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
