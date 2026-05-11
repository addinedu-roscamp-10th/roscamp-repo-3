import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QFrame, QStackedWidget


_APP = None
REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN_QSS = REPO_ROOT / "ui" / "utils" / "styles" / "main.qss"


NAV_ITEMS = [
    ("home", "홈"),
    ("task_request", "작업 요청"),
    ("task_monitor", "작업 모니터"),
    ("coordinate_settings", "좌표/구역 설정"),
    ("robot_status", "로봇 상태"),
    ("inventory", "재고 관리"),
    ("patient", "어르신 정보"),
    ("alerts", "알림/로그"),
]


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def test_shared_admin_shell_components_expose_ropi_contract():
    _app()

    from ui.utils.widgets.admin_shell import (
        AdminSidebar,
        PageHeader,
        PageTimeCard,
        SystemStatusStrip,
    )

    sidebar = AdminSidebar(nav_items=NAV_ITEMS, user_name="테스트 운영자")
    header = PageHeader(title="작업 현황", subtitle="전체 시나리오 상태")
    time_card = PageTimeCard(show_last_update=False)
    status_header = PageHeader(
        title="서비스 상태",
        subtitle="서비스 연결 상태",
        show_status=True,
    )
    default_status_strip = SystemStatusStrip()
    status_strip = SystemStatusStrip({"Control Service": "online", "DB": "warning"})

    try:
        assert sidebar.objectName() == "adminSidebar"
        assert sidebar.findChild(QLabel, "sidebarBrand").text() == "ROPI"
        assert sidebar.findChild(QLabel, "userName").text() == "테스트 운영자"
        sidebar_labels = _label_texts(sidebar)
        assert "관제 운영자" in sidebar_labels
        assert all("요양보호사" not in text for text in sidebar_labels)

        side_buttons = [
            button.text()
            for button in sidebar.findChildren(QPushButton)
            if button.objectName() == "sideButton"
        ]
        assert side_buttons == [label for _, label in NAV_ITEMS]

        assert header.objectName() == "pageHeader"
        assert header.findChild(QLabel, "pageHeaderEyebrow") is None
        assert header.findChild(QLabel, "pageTitle").text() == "작업 현황"
        assert header.findChild(QLabel, "pageSubtitle").text() == "전체 시나리오 상태"
        assert header.findChild(QFrame, "systemStatusStrip") is None
        assert time_card.objectName() == "pageTimeCard"
        assert time_card.findChild(QLabel, "timeCardClock").text()
        assert time_card.findChild(QLabel, "timeCardDate").text()
        assert time_card.last_update_label.isHidden() is False
        assert time_card.last_update_label.text() == " "
        assert status_header.findChild(QFrame, "systemStatusStrip") is not None

        assert status_strip.objectName() == "systemStatusStrip"
        assert status_strip.findChild(QLabel, "systemStatusOnline") is not None
        assert status_strip.findChild(QLabel, "systemStatusWarning") is not None

        default_status_labels = _label_texts(default_status_strip)
        assert "관제 서버 확인 중" in default_status_labels
        assert "데이터베이스 확인 중" in default_status_labels
        assert "AI 서버 확인 중" in default_status_labels
        assert all("Control Service" not in text for text in default_status_labels)
        assert all("AI Server" not in text for text in default_status_labels)
    finally:
        sidebar.close()
        header.close()
        time_card.close()
        status_header.close()
        default_status_strip.close()
        status_strip.close()


def test_page_time_card_keeps_stable_size_for_different_page_actions():
    _app()

    from ui.utils.widgets.admin_shell import (
        ADMIN_SIDEBAR_WIDTH,
        PAGE_TIME_CARD_ACTION_ROW_HEIGHT,
        PAGE_TIME_CARD_CLOCK_ROW_HEIGHT,
        PAGE_TIME_CARD_HEIGHT,
        PAGE_TIME_CARD_META_ROW_HEIGHT,
        PAGE_TIME_CARD_STATUS_ROW_HEIGHT,
        PAGE_TIME_CARD_WIDTH,
        PAGE_TIME_CARD_BUTTON_HEIGHT,
        PageTimeCard,
    )

    plain_card = PageTimeCard(show_last_update=False)
    refresh_card = PageTimeCard(refresh_text="새로고침")
    stream_card = PageTimeCard(
        status_text="이벤트 스트림 연결 대기",
        refresh_text="새로고침",
    )
    coordinate_card = PageTimeCard(show_last_update=False)
    coordinate_card.add_action(QPushButton("새로고침"))
    coordinate_card.add_action(QPushButton("변경 취소"))
    coordinate_card.add_action(QPushButton("저장"))
    stream_card.add_action(QPushButton("스트림 재연결"))

    cards = [plain_card, refresh_card, stream_card, coordinate_card]

    try:
        for card in cards:
            assert card.minimumWidth() == PAGE_TIME_CARD_WIDTH
            assert card.maximumWidth() == PAGE_TIME_CARD_WIDTH
            assert card.minimumHeight() == PAGE_TIME_CARD_HEIGHT
            assert card.maximumHeight() == PAGE_TIME_CARD_HEIGHT
            assert card.last_update_label.isHidden() is False
            assert card.status_label.isHidden() is False
            assert card.action_row.objectName() == "timeCardActionRow"
            assert card.action_row.minimumHeight() == card.action_row.maximumHeight()
            assert card.action_row.minimumHeight() >= PAGE_TIME_CARD_BUTTON_HEIGHT
            for button in card.action_row.findChildren(QPushButton):
                assert button.minimumHeight() == PAGE_TIME_CARD_BUTTON_HEIGHT
                assert button.maximumHeight() == PAGE_TIME_CARD_BUTTON_HEIGHT
                assert PAGE_TIME_CARD_BUTTON_HEIGHT >= 40

        assert len({card.sizeHint().height() for card in cards}) == 1
        assert len({card.sizeHint().width() for card in cards}) == 1
        assert PAGE_TIME_CARD_WIDTH <= 340
        assert ADMIN_SIDEBAR_WIDTH <= 240
        _, top_margin, _, bottom_margin = plain_card.layout().getContentsMargins()
        required_height = (
            top_margin
            + bottom_margin
            + PAGE_TIME_CARD_CLOCK_ROW_HEIGHT
            + PAGE_TIME_CARD_META_ROW_HEIGHT * 2
            + PAGE_TIME_CARD_STATUS_ROW_HEIGHT
            + PAGE_TIME_CARD_ACTION_ROW_HEIGHT
            + plain_card.layout().spacing() * 4
        )
        assert PAGE_TIME_CARD_HEIGHT - required_height >= 16

        qss = MAIN_QSS.read_text(encoding="utf-8")
        assert "QWidget#timeCardActionRow QPushButton" in qss
        action_button_qss = qss.split("QWidget#timeCardActionRow QPushButton", 1)[
            1
        ].split("}", 1)[0]
        assert "padding: 4px 10px;" in action_button_qss
        assert "min-height:" not in action_button_qss
        assert "max-height:" not in action_button_qss
        assert f"min-width: {ADMIN_SIDEBAR_WIDTH}px" in qss
        assert f"max-width: {ADMIN_SIDEBAR_WIDTH}px" in qss
    finally:
        for card in cards:
            card.close()


def test_caregiver_main_window_uses_shared_admin_shell_contract():
    _app()

    from ui.admin_ui.main_window import CaregiverMainWindow
    from ui.utils.widgets.admin_shell import ADMIN_SIDEBAR_WIDTH

    window = CaregiverMainWindow()

    try:
        assert window.windowTitle() == "ROPI 관제 콘솔"
        assert hasattr(window, "admin_shell")
        sidebar = window.findChild(QFrame, "adminSidebar")
        assert sidebar is not None
        assert sidebar.minimumWidth() == ADMIN_SIDEBAR_WIDTH
        assert sidebar.maximumWidth() == ADMIN_SIDEBAR_WIDTH
        assert window.findChild(QStackedWidget, "adminPageStack") is window.stack
        assert not hasattr(window, "system_health_btn")
        assert not hasattr(window, "system_health_page")

        brand = window.findChild(QLabel, "sidebarBrand")
        assert brand is not None
        assert brand.text() == "ROPI"

        labels = _label_texts(window)
        assert "관제 운영자" in labels
        assert all("요양보호사" not in text for text in labels)
        assert all("CareBot" not in text for text in labels)
        assert all("RoboCare" not in text for text in labels)
        assert all("OPERATIONAL CONSOLE" not in text for text in labels)

        side_buttons = [
            button.text()
            for button in sidebar.findChildren(QPushButton)
            if button.objectName() == "sideButton"
        ]
        assert side_buttons == [label for _, label in NAV_ITEMS]
    finally:
        window.close()


def test_admin_login_visible_copy_uses_operator_wording():
    source_path = (
        Path(__file__).resolve().parents[3] / "ui" / "admin_ui" / "login_auth_window.py"
    )
    source = source_path.read_text(encoding="utf-8")

    assert "ROPI 관제 운영자 로그인" in source
    assert "관제 운영 콘솔" in source
    assert "관제 운영자 로그인" in source
    assert "요양보호사" not in source


def test_caregiver_common_shell_routes_placeholder_pages():
    _app()

    from ui.admin_ui.main_window import CaregiverMainWindow

    window = CaregiverMainWindow()

    try:
        window.task_monitor_btn.click()
        assert window.task_monitor_page is not None
        assert window.stack.currentWidget() is window.task_monitor_page
        assert window.task_monitor_btn.isChecked()

        window.coordinate_settings_btn.click()
        assert window.coordinate_settings_page is not None
        assert window.stack.currentWidget() is window.coordinate_settings_page
        assert window.coordinate_settings_btn.isChecked()
    finally:
        window.close()


def test_caregiver_coordinate_settings_page_autoloads_on_first_entry(monkeypatch):
    _app()

    from ui.admin_ui.main_window import CaregiverMainWindow
    from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
        CoordinateZoneSettingsPage,
    )

    load_calls = []

    def fake_load_coordinate_bundle(self):
        load_calls.append(self)

    monkeypatch.setattr(
        CoordinateZoneSettingsPage,
        "load_coordinate_bundle",
        fake_load_coordinate_bundle,
    )

    window = CaregiverMainWindow()

    try:
        window.coordinate_settings_btn.click()

        assert load_calls == [window.coordinate_settings_page]
    finally:
        window.close()


def test_caregiver_shell_pages_use_common_page_header():
    _app()

    from ui.admin_ui.main_window import CaregiverMainWindow
    from ui.utils.widgets.admin_shell import PageHeader, PageTimeCard

    window = CaregiverMainWindow()

    window.home_page.load_dashboard_data = lambda: None

    routes = [
        ("home", None),
        ("task_request", window.task_btn),
        ("task_monitor", window.task_monitor_btn),
        ("coordinate_settings", window.coordinate_settings_btn),
        ("robot_status", window.robot_status_btn),
        ("inventory", window.inventory_btn),
        ("patient", window.patient_btn),
        ("alerts", window.alert_btn),
    ]

    try:
        for _key, button in routes:
            if button is not None:
                button.click()
            current_page = window.stack.currentWidget()
            assert current_page.findChild(PageHeader, "pageHeader") is not None
            assert current_page.findChild(PageTimeCard) is not None

        labels = _label_texts(window)
        assert "Task Request" not in labels
        assert "Inventory" not in labels
        assert "Patient Info" not in labels
        assert "실시간 연결" not in labels
        assert "date / 알림 / 오류 확인" not in labels
    finally:
        window.close()


def test_caregiver_shell_status_strip_only_appears_on_status_context_pages():
    _app()

    from ui.admin_ui.main_window import CaregiverMainWindow

    window = CaregiverMainWindow()
    window.home_page.load_dashboard_data = lambda: None

    routes = [
        ("home", None, True),
        ("task_request", window.task_btn, False),
        ("task_monitor", window.task_monitor_btn, False),
        ("coordinate_settings", window.coordinate_settings_btn, False),
        ("robot_status", window.robot_status_btn, False),
        ("inventory", window.inventory_btn, False),
        ("patient", window.patient_btn, False),
        ("alerts", window.alert_btn, False),
    ]

    try:
        for _key, button, expected_visible in routes:
            if button is not None:
                button.click()
            current_page = window.stack.currentWidget()
            has_status_strip = (
                current_page.findChild(QFrame, "systemStatusStrip") is not None
            )
            assert has_status_strip is expected_visible
    finally:
        window.close()


def test_caregiver_main_window_fans_out_admin_event_stream(monkeypatch):
    _app()

    from ui.admin_ui.main_window import CaregiverMainWindow
    from ui.utils.pages.caregiver.alert_log_page import AlertLogPage
    from ui.utils.pages.caregiver.delivery_request_form import DeliveryRequestForm
    from ui.utils.pages.caregiver.robot_status_page import RobotStatusPage

    monkeypatch.setattr(DeliveryRequestForm, "ensure_items_loaded", lambda self: None)
    monkeypatch.setattr(RobotStatusPage, "refresh_data", lambda self: None)
    monkeypatch.setattr(AlertLogPage, "refresh_data", lambda self: None)

    window = CaregiverMainWindow()
    received = []

    try:
        window.home_page.apply_stream_event = lambda event: received.append(
            ("home", event["event_type"])
        )
        window.task_btn.click()
        window.task_page.apply_stream_event = lambda event: received.append(
            ("task_request", event["event_type"])
        )
        window.robot_status_btn.click()
        window.robot_status_page.apply_stream_event = lambda event: received.append(
            ("robot_status", event["event_type"])
        )
        window.alert_btn.click()
        window.alert_page.apply_stream_event = lambda event: received.append(
            ("alerts", event["event_type"])
        )

        window._handle_admin_event_batch(
            {
                "batch_end_seq": 7,
                "events": [
                    {"event_type": "TASK_UPDATED", "payload": {"task_id": 101}},
                    {
                        "event_type": "PINKY_UPDATED",
                        "payload": {"pinky_id": "pinky2"},
                    },
                ],
            }
        )

        assert window._admin_event_last_seq == 7
        assert received == [
            ("home", "TASK_UPDATED"),
            ("task_request", "TASK_UPDATED"),
            ("robot_status", "TASK_UPDATED"),
            ("alerts", "TASK_UPDATED"),
            ("home", "PINKY_UPDATED"),
            ("task_request", "PINKY_UPDATED"),
            ("robot_status", "PINKY_UPDATED"),
            ("alerts", "PINKY_UPDATED"),
        ]
    finally:
        window.close()


def test_caregiver_main_window_restarts_admin_event_stream_after_failure(
    monkeypatch,
):
    _app()

    import ui.admin_ui.main_window as main_window
    from ui.admin_ui.main_window import CaregiverMainWindow

    scheduled = []
    restart_calls = []

    window = CaregiverMainWindow()

    monkeypatch.setattr(
        main_window.QTimer,
        "singleShot",
        lambda delay_ms, callback: scheduled.append((delay_ms, callback)),
    )

    try:
        window._start_admin_event_stream = lambda: restart_calls.append("restart")
        window._admin_event_stream_enabled = True

        window._handle_admin_event_stream_failed("connection failed")
        window._clear_admin_event_stream_thread()

        assert scheduled == [(1000, window._start_admin_event_stream)]

        scheduled[0][1]()

        assert restart_calls == ["restart"]
    finally:
        window.close()
