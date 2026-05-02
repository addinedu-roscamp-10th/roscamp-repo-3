from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, QDateTime, QObject, QThread, pyqtSignal

from ui.utils.network.service_clients import CaregiverRemoteService
from ui.utils.session.session_manager import SessionManager
from ui.utils.widgets.admin_shell import AdminShell, PageHeader, PlaceholderPage


class DashboardLoadWorker(QObject):
    finished = pyqtSignal(object, object, object, object, object)

    def run(self):
        try:
            bundle = CaregiverRemoteService().get_dashboard_bundle()
            summary = bundle.get("summary", {})
            robots = bundle.get("robots", [])
            flow_data = bundle.get("flow_data", {})
            timeline_rows = bundle.get("timeline_rows", [])
            self.finished.emit(True, summary, robots, flow_data, timeline_rows)
        except Exception as exc:
            self.finished.emit(False, str(exc), [], {}, [])


class StatusChip(QLabel):
    def __init__(self, text: str, chip_type: str = "green"):
        super().__init__(text)
        mapping = {
            "green": "chipGreen",
            "blue": "chipBlue",
            "red": "chipRed",
            "yellow": "chipYellow",
        }
        self.setObjectName(mapping.get(chip_type, "chipBlue"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class RobotBoardCard(QFrame):
    def __init__(
        self,
        robot_name: str,
        status: str,
        zone: str,
        battery: str,
        current_task: str = "-",
        chip_type: str = "green"
    ):
        super().__init__()
        self.setObjectName("card")

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        top = QHBoxLayout()
        name = QLabel(robot_name)
        name.setObjectName("sectionTitle")
        chip = StatusChip(status, chip_type)

        top.addWidget(name)
        top.addStretch()
        top.addWidget(chip)

        current_task_label = QLabel(f"현재 작업: {current_task}")
        current_task_label.setObjectName("mutedText")

        zone_label = QLabel(f"현재 구역: {zone}")
        zone_label.setObjectName("mutedText")

        battery_label = QLabel(f"배터리: {battery}")
        battery_label.setObjectName("mutedText")

        root.addLayout(top)
        root.addWidget(current_task_label)
        root.addWidget(zone_label)
        root.addWidget(battery_label)


class FlowColumn(QFrame):
    def __init__(self, title: str, tasks: list):
        super().__init__()
        self.setObjectName("card")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")

        count_label = QLabel(f"{len(tasks)} task(s)")
        count_label.setObjectName("mutedText")

        root.addWidget(title_label)
        root.addWidget(count_label)

        if tasks:
            for task in tasks:
                task_card = QFrame()
                task_card.setObjectName("infoBox")
                tc = QVBoxLayout(task_card)
                tc.setContentsMargins(12, 12, 12, 12)
                task_label = QLabel(self._format_task_label(task))
                task_label.setWordWrap(True)
                tc.addWidget(task_label)
                root.addWidget(task_card)
        else:
            empty = QLabel("현재 비어 있음")
            empty.setObjectName("mutedText")
            root.addWidget(empty)

        root.addStretch()

    @staticmethod
    def _format_task_label(task):
        if not isinstance(task, dict):
            return str(task)

        display_text = str(task.get("display_text") or "").strip()
        feedback_summary = str(task.get("feedback_summary") or "").strip()
        if display_text and feedback_summary:
            return f"{display_text}\n{feedback_summary}"
        if display_text:
            return display_text

        task_id = task.get("task_id") or "-"
        description = task.get("description") or "-"
        robot_id = task.get("robot_id") or "-"
        fallback = f"#{task_id} {description} / {robot_id}"
        if feedback_summary:
            return f"{fallback}\n{feedback_summary}"
        return fallback


class CaregiverHomePage(QWidget):
    def __init__(self):
        super().__init__()
        self.summary_value_labels = []
        self.robot_row = None
        self.timeline_table = None
        self.flow_grid = None
        self.dashboard_thread = None
        self.dashboard_worker = None

        self._build_ui()
        QTimer.singleShot(0, self.load_dashboard_data)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        top = QHBoxLayout()

        time_box = QFrame()
        time_box.setObjectName("card")
        tb = QVBoxLayout(time_box)
        tb.setContentsMargins(18, 16, 18, 16)

        self.t1 = QLabel()
        self.t1.setObjectName("summaryValue")
        self.t2 = QLabel()
        self.t2.setObjectName("mutedText")

        tb.addWidget(self.t1, alignment=Qt.AlignmentFlag.AlignRight)
        tb.addWidget(self.t2, alignment=Qt.AlignmentFlag.AlignRight)

        top.addWidget(
            PageHeader(
                "보호사 메인 화면",
                "현재 로봇 상태와 작업 흐름을 한눈에 확인하세요.",
                show_status=True,
            ),
            1,
        )
        top.addWidget(time_box)

        def update_time():
            now = QDateTime.currentDateTime()
            self.t1.setText(now.toString("HH:mm:ss"))
            self.t2.setText(now.toString("yyyy.MM.dd"))

        self.timer = QTimer(self)
        self.timer.timeout.connect(update_time)
        self.timer.start(1000)
        update_time()

        summary_row = QHBoxLayout()
        summary_row.setSpacing(16)

        summary_titles = ["사용가능 로봇", "대기 작업", "수행 중 작업"]

        for title_text in summary_titles:
            card = QFrame()
            card.setObjectName("card")

            c = QVBoxLayout(card)
            c.setContentsMargins(18, 18, 18, 18)

            lbl1 = QLabel(title_text)
            lbl1.setObjectName("mutedText")

            lbl2 = QLabel("0")
            lbl2.setObjectName("summaryValue")

            c.addWidget(lbl1)
            c.addWidget(lbl2)
            summary_row.addWidget(card)

            self.summary_value_labels.append(lbl2)

        robot_board_wrap = QFrame()
        robot_board_wrap.setObjectName("card")
        rbw = QVBoxLayout(robot_board_wrap)
        rbw.setContentsMargins(20, 20, 20, 20)
        rbw.setSpacing(14)

        robot_title = QLabel("로봇 보드")
        robot_title.setObjectName("sectionTitle")

        self.robot_row = QHBoxLayout()
        self.robot_row.setSpacing(16)

        rbw.addWidget(robot_title)
        rbw.addLayout(self.robot_row)

        flow_wrap = QFrame()
        flow_wrap.setObjectName("card")
        fw = QVBoxLayout(flow_wrap)
        fw.setContentsMargins(20, 20, 20, 20)
        fw.setSpacing(14)

        flow_title = QLabel("Task Flow Board")
        flow_title.setObjectName("sectionTitle")

        flow_sub = QLabel("현재 요청된 작업을 상태별로 분류해 보여줍니다.")
        flow_sub.setObjectName("mutedText")

        self.flow_grid = QGridLayout()
        self.flow_grid.setHorizontalSpacing(16)
        self.flow_grid.setVerticalSpacing(16)

        fw.addWidget(flow_title)
        fw.addWidget(flow_sub)
        fw.addLayout(self.flow_grid)

        timeline_wrap = QFrame()
        timeline_wrap.setObjectName("card")
        tw = QVBoxLayout(timeline_wrap)
        tw.setContentsMargins(20, 20, 20, 20)
        tw.setSpacing(12)

        timeline_title = QLabel("작업 타임라인")
        timeline_title.setObjectName("sectionTitle")

        self.timeline_table = QTableWidget(0, 4)
        self.timeline_table.setHorizontalHeaderLabels(["시간", "작업 ID", "이벤트", "상세"])
        self.timeline_table.horizontalHeader().setStretchLastSection(True)

        tw.addWidget(timeline_title)
        tw.addWidget(self.timeline_table)

        root.addLayout(top)
        root.addLayout(summary_row)
        root.addWidget(robot_board_wrap)
        root.addWidget(flow_wrap)
        root.addWidget(timeline_wrap, 1)

    def load_dashboard_data(self):
        if self.dashboard_thread is not None:
            return

        self.dashboard_thread = QThread(self)
        self.dashboard_worker = DashboardLoadWorker()
        self.dashboard_worker.moveToThread(self.dashboard_thread)

        self.dashboard_thread.started.connect(self.dashboard_worker.run)
        self.dashboard_worker.finished.connect(self._handle_dashboard_loaded)
        self.dashboard_worker.finished.connect(self.dashboard_thread.quit)
        self.dashboard_worker.finished.connect(self.dashboard_worker.deleteLater)
        self.dashboard_thread.finished.connect(self.dashboard_thread.deleteLater)
        self.dashboard_thread.finished.connect(self._clear_dashboard_thread)

        self.dashboard_thread.start()

    def _handle_dashboard_loaded(self, ok, summary, robots, flow_data, timeline_rows):
        if not ok:
            print(f"[ERROR] 대시보드 데이터 로드 실패: {summary}")
            return

        self.apply_summary_data(summary)
        self.apply_robot_board_data(robots)
        self.apply_flow_board_data(flow_data)
        self.apply_timeline_data(timeline_rows)

    def _clear_dashboard_thread(self):
        self.dashboard_thread = None
        self.dashboard_worker = None

    def apply_summary_data(self, summary):
        values = [
            f"{summary['available_robot_count']}대",
            f"{summary['waiting_job_count']}건",
            f"{summary['running_job_count']}건",
        ]

        for i, value in enumerate(values):
            if i < len(self.summary_value_labels):
                self.summary_value_labels[i].setText(value)

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()

            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self.clear_layout(child_layout)

    def clear_grid_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()

            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                self.clear_layout(child_layout)

    def apply_robot_board_data(self, robots):
        self.clear_layout(self.robot_row)

        for robot in robots:
            card = RobotBoardCard(
                robot_name=robot["robot_name"],
                status=robot["status"],
                zone=robot["zone"],
                battery=robot["battery"],
                current_task=robot["current_task"],
                chip_type=robot["chip_type"]
            )
            self.robot_row.addWidget(card)

    def apply_flow_board_data(self, flow_data):
        self.clear_grid_layout(self.flow_grid)

        self.flow_grid.addWidget(FlowColumn("READY HELP", flow_data.get("READY", [])), 0, 0)
        self.flow_grid.addWidget(FlowColumn("ASSIGNED", flow_data.get("ASSIGNED", [])), 0, 1)
        self.flow_grid.addWidget(FlowColumn("RUNNING", flow_data.get("RUNNING", [])), 0, 2)
        self.flow_grid.addWidget(FlowColumn("DONE", flow_data.get("DONE", [])), 0, 3)

    def apply_timeline_data(self, rows):
        self.timeline_table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self.timeline_table.setItem(r, c, QTableWidgetItem(str(value)))


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
        ("system_health", "시스템 상태"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("보호사 메인")
        self.login_window = None
        self.task_page = None
        self.task_monitor_page = None
        self.coordinate_settings_page = None
        self.robot_status_page = None
        self.inventory_page = None
        self.patient_page = None
        self.alert_page = None
        self.system_health_page = None
        self._build_ui()
        self._fit_to_screen()

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        current_user = SessionManager.current_user()
        user_name = current_user.name if current_user else "김보호 보호사"

        self.admin_shell = AdminShell(
            nav_items=self.NAV_ITEMS,
            user_name=user_name,
            user_role="요양보호사",
            on_logout=self.logout,
        )
        self.shell = self.admin_shell
        self.admin_shell.nav_requested.connect(self._handle_nav)

        self.stack = self.admin_shell.stack
        self.page_scroll = self.admin_shell.page_scroll
        self.home_page = CaregiverHomePage()

        self.admin_shell.add_page("home", self.home_page)
        self.admin_shell.set_page("home")

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
        self.system_health_btn = self.admin_shell.sidebar.button("system_health")

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
            "system_health": self.show_system_health_page,
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
        from ui.utils.pages.caregiver.inventory_management_page import InventoryManagementPage
        self._show_or_create_page("inventory_page", InventoryManagementPage, "inventory")

    def show_patient_page(self):
        from ui.utils.pages.caregiver.patient_info_page import PatientInfoPage
        self._show_or_create_page("patient_page", PatientInfoPage, "patient")

    def show_alert_page(self):
        from ui.utils.pages.caregiver.alert_log_page import AlertLogPage
        self._show_or_create_page("alert_page", AlertLogPage, "alerts")

    def show_system_health_page(self):
        self._show_or_create_page(
            "system_health_page",
            lambda: PlaceholderPage(
                "시스템 상태",
                "관제 서버, 데이터베이스, ROS2, AI 서버의 연결 상태를 확인합니다.",
                show_status=True,
            ),
            "system_health",
        )

    def closeEvent(self, event):
        for page in [
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
