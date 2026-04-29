import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _visible_texts(widget) -> list[str]:
    texts: list[str] = []
    for label in widget.findChildren(QLabel):
        texts.append(label.text())
    for button in widget.findChildren(QPushButton):
        texts.append(button.text())
    return texts


def test_admin_app_entrypoint_uses_caregiver_login_not_role_picker(monkeypatch):
    _app()

    from ui.admin_ui import main as admin_main
    from ui.admin_ui.login_auth_window import LoginAuthWindow
    from ui.utils.network.heartbeat import HeartbeatMonitor

    monkeypatch.setattr(HeartbeatMonitor, "start", lambda self: None)

    window = admin_main.create_initial_window()

    try:
        assert isinstance(window, LoginAuthWindow)
        assert window.role == "caregiver"
    finally:
        window.close()


def test_caregiver_login_window_is_caregiver_only_product_entry(monkeypatch):
    _app()

    from ui.admin_ui import login_auth_window

    if hasattr(login_auth_window, "HeartbeatMonitor"):
        monkeypatch.setattr(
            login_auth_window.HeartbeatMonitor,
            "start",
            lambda self: None,
        )

    window = login_auth_window.LoginAuthWindow()

    try:
        texts = _visible_texts(window)

        assert window.role == "caregiver"
        assert window.objectName() == "loginAuthRoot"
        assert window.findChild(QLabel, "loginBrandTitle").text() == "ROPI"
        assert window.findChild(QLabel, "loginServerStatus") is not None
        assert window.id_input.placeholderText() == "요양보호사 ID 입력"
        assert window.pw_input.placeholderText() == "비밀번호 입력"
        assert window.login_btn.text() == "로그인"
        assert "뒤로가기" not in texts
        assert all("방문객" not in text and "방문자" not in text for text in texts)
    finally:
        window.close()


def test_caregiver_logout_returns_to_caregiver_login_not_role_picker(monkeypatch):
    _app()

    from ui.admin_ui import login_auth_window
    from ui.admin_ui.main_window import CaregiverMainWindow
    from ui.utils.network.heartbeat import HeartbeatMonitor

    monkeypatch.setattr(login_auth_window.LoginAuthWindow, "show", lambda self: None)
    monkeypatch.setattr(HeartbeatMonitor, "start", lambda self: None)

    window = CaregiverMainWindow()

    try:
        window.logout()
        assert isinstance(window.login_window, login_auth_window.LoginAuthWindow)
        assert window.login_window.role == "caregiver"
    finally:
        if window.login_window is not None:
            window.login_window.close()
        window.close()


def test_visitor_kiosk_logout_resets_home_without_role_picker(monkeypatch):
    _app()

    from ui.user_ui.main_window import VisitorMainWindow
    from ui.utils.network.heartbeat import HeartbeatMonitor

    monkeypatch.setattr(HeartbeatMonitor, "start", lambda self: None)

    window = VisitorMainWindow()

    try:
        window.stack.setCurrentWidget(window.call_page)
        window.logout()

        assert window.login_window is None
        assert window.stack.currentWidget() is window.home_page
    finally:
        if window.login_window is not None:
            window.login_window.close()
        window.close()
