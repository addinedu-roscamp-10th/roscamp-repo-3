import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QGridLayout, QTextEdit

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

        assert page.preview_caregiver_id.text() == "caregiver_id: 7"
        assert page.preview_item.text() == "item_id: 1 / 세면도구 세트"
        assert page.preview_quantity.text() == "quantity: 2"
        assert page.preview_destination.text() == "destination_id: delivery_room_301"
        assert page.preview_priority.text() == "priority: URGENT"
        assert all("task_id" not in text.lower() for text in _label_texts(page.preview_card))
    finally:
        SessionManager.logout()
        page.close()


def test_delivery_form_uses_wireframe_form_controls():
    _app()

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
        assert priority_buttons == ["NORMAL", "URGENT", "HIGHEST"]
        assert form.get_priority_code() == "NORMAL"

        form.set_priority("URGENT")
        assert form.get_priority_code() == "URGENT"
        assert form.priority_buttons["URGENT"].isChecked() is True

        notes = form.findChild(QTextEdit, "deliveryNotesInput")
        assert notes is form.detail_input
        assert notes.minimumHeight() <= 88
        assert notes.maximumHeight() <= 88
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

        assert page.result_code_label.text() == "result_code: ACCEPTED"
        assert page.result_message_label.text() == "작업이 접수되었습니다."
        assert page.reason_code_label.text() == "reason_code: -"
        assert page.task_id_label.text() == "task_id: 1001"
        assert page.task_status_label.text() == "task_status: WAITING_DISPATCH"
        assert page.assigned_robot_id_label.text() == "assigned_robot_id: pinky2"

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

        assert page.result_code_label.text() == "result_code: REJECTED"
        assert page.result_message_label.text() == "재고가 부족합니다."
        assert page.reason_code_label.text() == "reason_code: ITEM_QUANTITY_INSUFFICIENT"
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
