import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QFrame, QStackedWidget


_APP = None


NAV_ITEMS = [
    ("home", "홈"),
    ("task_request", "작업 요청"),
    ("task_monitor", "작업 모니터"),
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
        assert header.findChild(QLabel, "pageTitle").text() == "작업 현황"
        assert header.findChild(QLabel, "pageSubtitle").text() == "전체 시나리오 상태"
        assert header.findChild(QFrame, "systemStatusStrip") is not None

        assert status_strip.objectName() == "systemStatusStrip"
        assert status_strip.findChild(QLabel, "systemStatusOnline") is not None
        assert status_strip.findChild(QLabel, "systemStatusWarning") is not None
    finally:
        sidebar.close()
        header.close()
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
