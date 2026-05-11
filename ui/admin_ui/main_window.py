from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout

from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage
from ui.utils.core.stream_refresh import StreamReconnectState
from ui.utils.core.worker_threads import start_worker_thread
from ui.utils.pages.caregiver.task_event_stream_worker import TaskEventStreamWorker
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.admin_shell import AdminShell


class CaregiverMainWindow(QMainWindow):
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

    def __init__(self, *, event_stream_enabled=False):
        super().__init__()
        self.setWindowTitle("ROPI 관제 콘솔")
        self.login_window = None
        self.task_page = None
        self.task_monitor_page = None
        self.coordinate_settings_page = None
        self.robot_status_page = None
        self.inventory_page = None
        self.patient_page = None
        self.alert_page = None
        self.admin_event_thread = None
        self.admin_event_worker = None
        self._admin_event_last_seq = 0
        self._admin_event_stream_enabled = bool(event_stream_enabled)
        self.admin_event_reconnect = StreamReconnectState(delay_ms=1000)
        if not self._admin_event_stream_enabled:
            self.admin_event_reconnect.cancel()
        self._build_ui()
        self._fit_to_screen()
        if self._admin_event_stream_enabled:
            self._start_admin_event_stream()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        current_user = SessionManager.current_user()
        user_name = current_user.name if current_user else "관제 운영자"

        self.admin_shell = AdminShell(
            nav_items=self.NAV_ITEMS,
            user_name=user_name,
            user_role="관제 운영자",
            on_logout=self.logout,
        )
        self.shell = self.admin_shell
        self.admin_shell.nav_requested.connect(self._handle_nav)

        self.stack = self.admin_shell.stack
        self.home_page = CaregiverHomePage()

        self.admin_shell.add_page("home", self.home_page)
        self.admin_shell.set_page("home")
        self.page_scroll = self.admin_shell.page_scroll

        self.home_btn = self.admin_shell.sidebar.button("home")
        self.task_btn = self.admin_shell.sidebar.button("task_request")
        self.task_monitor_btn = self.admin_shell.sidebar.button("task_monitor")
        self.coordinate_settings_btn = self.admin_shell.sidebar.button(
            "coordinate_settings"
        )
        self.robot_status_btn = self.admin_shell.sidebar.button("robot_status")
        self.inventory_btn = self.admin_shell.sidebar.button("inventory")
        self.patient_btn = self.admin_shell.sidebar.button("patient")
        self.alert_btn = self.admin_shell.sidebar.button("alerts")

        layout.addWidget(self.admin_shell)

    def _fit_to_screen(self):
        screen = self.screen()
        if screen is None and self.windowHandle() is not None:
            screen = self.windowHandle().screen()
        if screen is None:
            from PyQt6.QtWidgets import QApplication

            screen = QApplication.primaryScreen()

        if screen is None:
            self.resize(1280, 800)
            return

        available = screen.availableGeometry()
        target_width = min(1480, max(1100, available.width() - 40))
        target_height = min(920, max(760, available.height() - 40))
        self.resize(target_width, target_height)

    def _show_or_create_page(self, attr_name, page_factory, page_key):
        page = getattr(self, attr_name)
        if page is None:
            page = page_factory()
            setattr(self, attr_name, page)
            self.admin_shell.add_page(page_key, page)
        if hasattr(page, "reset_page"):
            page.reset_page()
        self.admin_shell.set_page(page_key)
        self.page_scroll = self.admin_shell.page_scroll

    def _handle_nav(self, key):
        handlers = {
            "home": self.show_home_page,
            "task_request": self.show_task_page,
            "task_monitor": self.show_task_monitor_page,
            "coordinate_settings": self.show_coordinate_settings_page,
            "robot_status": self.show_robot_status_page,
            "inventory": self.show_inventory_page,
            "patient": self.show_patient_page,
            "alerts": self.show_alert_page,
        }
        handler = handlers.get(key)
        if handler is not None:
            handler()

    def logout(self):
        from ui.admin_ui.login_auth_window import LoginAuthWindow

        SessionManager.logout()
        self.login_window = LoginAuthWindow(role="caregiver")
        self.login_window.show()
        self.close()

    def show_home_page(self):
        self.admin_shell.set_page("home")
        self.page_scroll = self.admin_shell.page_scroll
        self.home_page.load_dashboard_data()

    def show_task_page(self):
        from ui.utils.pages.caregiver.task_request_page import TaskRequestPage

        self._show_or_create_page("task_page", TaskRequestPage, "task_request")

    def show_task_monitor_page(self):
        from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage

        self._show_or_create_page("task_monitor_page", TaskMonitorPage, "task_monitor")

    def show_coordinate_settings_page(self):
        from ui.utils.pages.caregiver.coordinate_zone_settings_page import (
            CoordinateZoneSettingsPage,
        )

        self._show_or_create_page(
            "coordinate_settings_page",
            CoordinateZoneSettingsPage,
            "coordinate_settings",
        )

    def show_robot_status_page(self):
        from ui.utils.pages.caregiver.robot_status_page import RobotStatusPage

        self._show_or_create_page("robot_status_page", RobotStatusPage, "robot_status")

    def show_inventory_page(self):
        from ui.utils.pages.caregiver.inventory_management_page import (
            InventoryManagementPage,
        )

        self._show_or_create_page(
            "inventory_page", InventoryManagementPage, "inventory"
        )

    def show_patient_page(self):
        from ui.utils.pages.caregiver.patient_info_page import PatientInfoPage

        self._show_or_create_page("patient_page", PatientInfoPage, "patient")

    def show_alert_page(self):
        from ui.utils.pages.caregiver.alert_log_page import AlertLogPage

        self._show_or_create_page("alert_page", AlertLogPage, "alerts")

    def _start_admin_event_stream(self):
        if not self._admin_event_stream_enabled:
            return
        if self.admin_event_thread is not None:
            return
        self.admin_event_reconnect.enable()
        self.admin_event_reconnect.reset_request()

        self.admin_event_thread, self.admin_event_worker = start_worker_thread(
            self,
            worker=TaskEventStreamWorker(
                consumer_id="ui-admin-console",
                last_seq=self._admin_event_last_seq,
            ),
            clear_handler=self._clear_admin_event_stream_thread,
            worker_signal_connections={
                "batch_received": self._handle_admin_event_batch,
                "failed": self._handle_admin_event_stream_failed,
            },
        )

    def _handle_admin_event_batch(self, batch):
        if not isinstance(batch, dict):
            return
        try:
            self._admin_event_last_seq = int(
                batch.get("batch_end_seq") or self._admin_event_last_seq
            )
        except (TypeError, ValueError):
            pass

        for event in batch.get("events") or []:
            if isinstance(event, dict):
                self._fanout_admin_stream_event(event)

    def _fanout_admin_stream_event(self, event):
        for page in self._iter_admin_stream_pages():
            handler = getattr(page, "apply_stream_event", None)
            if callable(handler):
                handler(event)

    def _iter_admin_stream_pages(self):
        seen_page_ids = set()
        for page in self.admin_shell.pages():
            if page is None:
                continue
            page_id = id(page)
            if page_id in seen_page_ids:
                continue
            seen_page_ids.add(page_id)
            if getattr(page, "uses_admin_event_stream", True) is False:
                continue
            if callable(getattr(page, "apply_stream_event", None)):
                yield page

    def _handle_admin_event_stream_failed(self, _error):
        if self._admin_event_stream_enabled:
            self.admin_event_reconnect.enable()
            self.admin_event_reconnect.request_restart()

    def _clear_admin_event_stream_thread(self):
        self.admin_event_thread = None
        self.admin_event_worker = None
        delay_ms = self.admin_event_reconnect.consume_restart_request()
        if self._admin_event_stream_enabled and delay_ms is not None:
            QTimer.singleShot(delay_ms, self._start_admin_event_stream)

    def _stop_admin_event_stream_thread(self):
        self._admin_event_stream_enabled = False
        self.admin_event_reconnect.cancel()
        worker = self.admin_event_worker
        thread = self.admin_event_thread
        if worker is not None:
            worker.stop()
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(1000)
        self._clear_admin_event_stream_thread()

    def closeEvent(self, event):
        self._stop_admin_event_stream_thread()
        for page in [
            self.home_page,
            self.task_page,
            self.task_monitor_page,
            self.coordinate_settings_page,
            self.robot_status_page,
            self.inventory_page,
            self.patient_page,
            self.alert_page,
        ]:
            shutdown = getattr(page, "shutdown", None)
            if shutdown is not None:
                shutdown()
        super().closeEvent(event)


__all__ = ["CaregiverMainWindow"]
