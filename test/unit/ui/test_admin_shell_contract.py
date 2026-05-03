import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QFrame, QStackedWidget


_APP = None


NAV_ITEMS = [
    ("home", "홈"),
    ("task_request", "작업 요청"),
    ("task_monitor", "작업 모니터"),
    ("coordinate_settings", "좌표/구역 설정"),
    ("robot_status", "로봇 상태"),
    ("inventory", "재고 관리"),
    ("patient", "어르신 정보"),
    ("alerts", "알림/로그"),
    ("system_health", "시스템 상태"),
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
        SystemStatusStrip,
    )

    sidebar = AdminSidebar(nav_items=NAV_ITEMS, user_name="테스트 보호사")
    header = PageHeader(title="작업 현황", subtitle="전체 시나리오 상태")
    status_header = PageHeader(
        title="시스템 상태",
        subtitle="서비스 연결 상태",
        show_status=True,
    )
    default_status_strip = SystemStatusStrip()
    status_strip = SystemStatusStrip({"Control Service": "online", "DB": "warning"})

    try:
        assert sidebar.objectName() == "adminSidebar"
        assert sidebar.findChild(QLabel, "sidebarBrand").text() == "ROPI"
        assert sidebar.findChild(QLabel, "userName").text() == "테스트 보호사"

        side_buttons = [
            button.text()
            for button in sidebar.findChildren(QPushButton)
            if button.objectName() == "sideButton"
        ]
        assert side_buttons == [label for _, label in NAV_ITEMS]

        assert header.objectName() == "pageHeader"
        assert header.findChild(QLabel, "pageHeaderEyebrow").text() == "관리자 콘솔"
        assert header.findChild(QLabel, "pageTitle").text() == "작업 현황"
        assert header.findChild(QLabel, "pageSubtitle").text() == "전체 시나리오 상태"
        assert header.findChild(QFrame, "systemStatusStrip") is None
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
        status_header.close()
        default_status_strip.close()
        status_strip.close()


def test_caregiver_main_window_uses_shared_admin_shell_contract():
    _app()

    from ui.admin_ui.main_window import CaregiverMainWindow

    window = CaregiverMainWindow()

    try:
        assert hasattr(window, "admin_shell")
        assert window.findChild(QFrame, "adminSidebar") is not None
        assert window.findChild(QStackedWidget, "adminPageStack") is window.stack

        brand = window.findChild(QLabel, "sidebarBrand")
        assert brand is not None
        assert brand.text() == "ROPI"

        labels = _label_texts(window)
        assert all("CareBot" not in text for text in labels)
        assert all("RoboCare" not in text for text in labels)
        assert all("OPERATIONAL CONSOLE" not in text for text in labels)

        sidebar = window.findChild(QFrame, "adminSidebar")
        side_buttons = [
            button.text()
            for button in sidebar.findChildren(QPushButton)
            if button.objectName() == "sideButton"
        ]
        assert side_buttons == [label for _, label in NAV_ITEMS]
    finally:
        window.close()


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

        window.system_health_btn.click()
        assert window.system_health_page is not None
        assert window.stack.currentWidget() is window.system_health_page
        assert window.system_health_btn.isChecked()
    finally:
        window.close()


def test_caregiver_shell_pages_use_common_page_header():
    _app()

    from ui.admin_ui.main_window import CaregiverMainWindow
    from ui.utils.widgets.admin_shell import PageHeader

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
        ("system_health", window.system_health_btn),
    ]

    try:
        for _key, button in routes:
            if button is not None:
                button.click()
            current_page = window.stack.currentWidget()
            assert current_page.findChild(PageHeader, "pageHeader") is not None

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
        ("system_health", window.system_health_btn, True),
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
