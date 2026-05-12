from __future__ import annotations

import math
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from ui.presentation_demo.admin_demo_data import (
    DemoAdminStore,
    DemoMapMarker,
    DemoSnapshot,
    DemoTask,
    build_admin_demo_snapshot,
    display_status,
)
from ui.presentation_demo.robot_display import (
    runtime_robot_id_for_display,
    translate_robot_display_payload,
)
from ui.utils.core.styles import load_stylesheet
from ui.utils.pages.caregiver.alert_log_page import AlertLogPage
from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage
from ui.utils.pages.caregiver.task_monitor_page import TaskMonitorPage
from ui.utils.pages.caregiver.task_request_page import TaskRequestPage
from ui.utils.widgets.admin_common import StatusChip, battery_text
from ui.utils.widgets.admin_shell import AdminShell, PageHeader, PageTimeCard
from ui.utils.widgets.map_canvas import MapCanvasWidget


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEMO_MAP_YAML = (
    PROJECT_ROOT
    / "device"
    / "ropi_mobile"
    / "src"
    / "ropi_nav_config"
    / "maps"
    / "map_test12_0506.yaml"
)
DEMO_MAP_PGM = DEMO_MAP_YAML.with_suffix(".pgm")
DEMO_MAP_CANVAS_SIZE = (528, 300)


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        widget = item.widget()
        if child_layout is not None:
            clear_layout(child_layout)
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def chip_type_for_tone(tone: str) -> str:
    return {
        "blue": "blue",
        "green": "green",
        "amber": "yellow",
        "red": "red",
    }.get(tone, "blue")


class PresentationHomeMapWidget(MapCanvasWidget):
    route_hint_enabled = False
    marker_outer_radius_px = 14
    marker_inner_radius_px = 6
    marker_heading_length_px = 15
    marker_label_width_px = 76
    marker_label_height_px = 34

    def __init__(self, markers: tuple[DemoMapMarker, ...], parent=None):
        super().__init__(parent)
        self.markers = markers
        self.setFixedSize(*DEMO_MAP_CANVAS_SIZE)
        self.load_map_from_paths(
            yaml_path=str(DEMO_MAP_YAML),
            pgm_path=str(DEMO_MAP_PGM),
            cache_key=("presentation-admin-demo", str(DEMO_MAP_YAML)),
        )

    @property
    def marker_count(self) -> int:
        return len(self.markers)

    def set_markers(self, markers: tuple[DemoMapMarker, ...]) -> None:
        self.markers = markers
        self.update()

    def draw_overlay(self, painter: QPainter, target):
        if self.route_hint_enabled:
            self._draw_route_hint(painter, target)
        for marker in self.markers:
            self._draw_marker(painter, target, marker)

    def _draw_route_hint(self, painter: QPainter, target) -> None:
        points = []
        for marker in self.markers:
            view_point = self._marker_view_point(marker, target)
            if view_point is not None:
                points.append(view_point)
        if len(points) < 2:
            return

        painter.setPen(QPen(QColor("#CBD5E1"), 2.0, Qt.PenStyle.DashLine))
        for start, end in zip(points, points[1:]):
            painter.drawLine(start, end)

    def _draw_marker(
        self,
        painter: QPainter,
        target,
        marker: DemoMapMarker,
    ) -> None:
        center = self._marker_view_point(marker, target)
        if center is None:
            return

        color = self._tone_color(marker.tone)
        painter.setPen(QPen(color.darker(115), 2.0))
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 55))
        painter.drawEllipse(
            center,
            self.marker_outer_radius_px,
            self.marker_outer_radius_px,
        )
        painter.setBrush(color)
        painter.drawEllipse(
            center,
            self.marker_inner_radius_px,
            self.marker_inner_radius_px,
        )

        heading = math.radians(marker.yaw_deg)
        nose = QPointF(
            center.x() + math.cos(heading) * self.marker_heading_length_px,
            center.y() - math.sin(heading) * self.marker_heading_length_px,
        )
        left = QPointF(
            center.x() + math.cos(heading + 2.45) * 8,
            center.y() - math.sin(heading + 2.45) * 8,
        )
        right = QPointF(
            center.x() + math.cos(heading - 2.45) * 8,
            center.y() - math.sin(heading - 2.45) * 8,
        )
        painter.drawPolygon(QPolygonF([nose, left, right]))

        label_rect = self._label_rect(center, target)
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(QPen(color, 1.3))
        painter.drawRoundedRect(label_rect, 10, 10)

        name_font = QFont()
        name_font.setPointSize(7)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor("#16202A"))
        painter.drawText(
            label_rect.adjusted(6, 2, -6, -18),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            marker.display_id,
        )

        detail_font = QFont()
        detail_font.setPointSize(6)
        detail_font.setBold(True)
        painter.setFont(detail_font)
        painter.setPen(color.darker(115))
        painter.drawText(
            label_rect.adjusted(6, 17, -6, -2),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            marker.mission,
        )

    def _marker_view_point(self, marker: DemoMapMarker, target):
        pixel = self.world_to_pixel({"x": marker.x, "y": marker.y, "yaw": marker.yaw})
        if pixel is None:
            return None
        return self.to_view_point(pixel, target)

    @staticmethod
    def _label_rect(center: QPointF, target):
        from PyQt6.QtCore import QRectF

        rect = QRectF(
            center.x() + 10,
            center.y() - 17,
            PresentationHomeMapWidget.marker_label_width_px,
            PresentationHomeMapWidget.marker_label_height_px,
        )
        if rect.right() > target.right() - 6:
            rect.moveRight(center.x() - 10)
        if rect.bottom() > target.bottom() - 6:
            rect.moveBottom(center.y() - 10)
        if rect.top() < target.top() + 6:
            rect.moveTop(center.y() + 10)
        return rect

    @staticmethod
    def _tone_color(tone: str) -> QColor:
        return {
            "blue": QColor("#2563EB"),
            "green": QColor("#16A34A"),
            "amber": QColor("#F59E0B"),
            "red": QColor("#DC2626"),
        }.get(tone, QColor("#64748B"))


class PresentationCompactTaskFlowItem(QFrame):
    def __init__(self, task: DemoTask, index: int):
        super().__init__()
        self.setObjectName("infoBox")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel(f"{index}. {task.title}")
        title.setObjectName("homeTaskTitle")
        title.setWordWrap(True)

        chip = StatusChip(display_status(task.status), chip_type_for_tone(task.tone))

        header.addWidget(title, 1)
        header.addWidget(chip, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        detail = QLabel(f"{task.robot_display_id} · {task.phase} · 목적지 {task.destination}")
        detail.setObjectName("homeTaskFieldDetail")
        detail.setWordWrap(True)
        root.addWidget(detail)


class PresentationCompactTaskFlowCard(QFrame):
    def __init__(self, tasks: tuple[DemoTask, ...]):
        super().__init__()
        self.setObjectName("card")
        self.setProperty("presentation_compact_flow", True)
        self.setMinimumWidth(360)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("작업 흐름 보드")
        title.setObjectName("sectionTitle")
        self.count_label = QLabel()
        self.count_label.setObjectName("mutedText")

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.count_label, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header)

        self.task_layout = QVBoxLayout()
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(12)
        root.addLayout(self.task_layout)
        root.addStretch()
        self.set_tasks(tasks)

    def set_tasks(self, tasks: tuple[DemoTask, ...]) -> None:
        clear_layout(self.task_layout)
        self.count_label.setText(f"진행 중 {len(tasks)}건")
        for index, task in enumerate(tasks, start=1):
            self.task_layout.addWidget(PresentationCompactTaskFlowItem(task, index))


class PresentationRobotBoardCard(QFrame):
    def __init__(self, robot: dict):
        super().__init__()
        self.setObjectName("homeRobotCard")
        self.setProperty(
            "connection_status",
            str(robot.get("connection_status") or "online").lower(),
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        header = QHBoxLayout()
        name = QLabel(str(robot.get("robot_id") or "-"))
        name.setObjectName("homeRobotTitle")
        chip = StatusChip(
            str(robot.get("status_label") or robot.get("connection_status") or "-"),
            str(robot.get("chip_type") or "green"),
        )
        header.addWidget(name)
        header.addStretch()
        header.addWidget(chip)
        root.addLayout(header)

        rows = (
            ("구분", str(robot.get("robot_type") or "-")),
            ("현재 작업", str(robot.get("current_task_name") or "-")),
            ("위치", str(robot.get("current_location") or "-")),
            ("배터리", battery_text(robot.get("battery_percent"))),
            ("마지막 수신", str(robot.get("last_seen_at") or "-")),
        )
        for key, value in rows:
            self._add_field_row(root, key, value)

    @staticmethod
    def _add_field_row(layout, key: str, value: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)

        key_label = QLabel(key)
        key_label.setObjectName("homeRobotFieldKey")
        key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel(value)
        value_label.setObjectName("homeRobotFieldValue")
        value_label.setWordWrap(True)

        row.addWidget(key_label, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(value_label, 1)
        layout.addLayout(row)


class PresentationHomePage(CaregiverHomePage):
    def __init__(self, store: DemoAdminStore):
        self.store = store
        self.snapshot = store.snapshot
        self.map_widget = None
        self.compact_flow_card = None
        super().__init__(autoload=False, auto_system_status_poll=False)
        self._insert_map_flow_row()
        self.refresh_from_store(store.snapshot)

    def _insert_map_flow_row(self) -> None:
        row = QFrame()
        row.setProperty("presentation_map_flow_row", True)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(16)

        map_card = QFrame()
        map_card.setObjectName("card")
        map_card.setProperty("presentation_home_map", True)
        map_card.setMaximumWidth(DEMO_MAP_CANVAS_SIZE[0] + 40)
        root = QVBoxLayout(map_card)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("운영 맵")
        title.setObjectName("sectionTitle")

        self.map_widget = PresentationHomeMapWidget(self.snapshot.map_markers)
        root.addWidget(title)
        root.addWidget(
            self.map_widget,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )

        self.compact_flow_card = PresentationCompactTaskFlowCard(self.snapshot.tasks[:3])
        row_layout.addWidget(
            map_card,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        row_layout.addWidget(self.compact_flow_card, 1, Qt.AlignmentFlag.AlignTop)

        self.layout().insertWidget(3, row)

        flow_wrap = self.flow_scroll.parentWidget()
        if flow_wrap is not None:
            flow_wrap.hide()

    def refresh_from_store(self, snapshot: DemoSnapshot) -> None:
        self.snapshot = snapshot
        if self.header.status_strip is not None:
            self.header.status_strip.set_statuses(
                {
                    "관제 서버": "online",
                    "데이터베이스": "online",
                    "ROS2": "online",
                    "AI 서버": "online",
                }
            )
        self.time_card.mark_updated()
        self.time_card.set_status("운영 데이터 로드 완료")
        running_count = sum(1 for task in snapshot.tasks if task.status == "RUNNING")
        warning_count = sum(
            1
            for alert in snapshot.alerts
            if alert.severity in {"WARNING", "ERROR", "CRITICAL"}
        )
        self.apply_summary_data(
            {
                "available_robot_count": 3,
                "total_robot_count": 3,
                "waiting_job_count": 0,
                "running_job_count": running_count,
                "warning_error_count": warning_count,
            },
            robots=self._robot_rows(),
        )
        self.apply_robot_board_data(self._robot_rows())
        self.apply_timeline_data(self._timeline_rows())
        if self.map_widget is not None:
            self.map_widget.set_markers(snapshot.map_markers)
        if self.compact_flow_card is not None:
            self.compact_flow_card.set_tasks(snapshot.tasks[:3])

    def apply_robot_board_data(self, robots):
        robot_rows = [
            dict(robot) if isinstance(robot, dict) else {}
            for robot in (robots or [])
        ]
        self._last_robots = robot_rows
        self.clear_layout(self.robot_row)

        if not robot_rows:
            empty = QLabel("표시할 로봇 상태가 없습니다.")
            empty.setObjectName("mutedText")
            self.robot_row.addWidget(empty)
            return

        for robot in robot_rows:
            self.robot_row.addWidget(PresentationRobotBoardCard(robot))

    def _robot_rows(self) -> list[dict]:
        return [
            {
                "robot_id": robot.display_id,
                "robot_type": "ROPI 이동 로봇",
                "connection_status": "ONLINE",
                "status_label": robot.status,
                "chip_type": "green" if robot.tone != "amber" else "yellow",
                "current_task_name": robot.task_name,
                "current_location": robot.location,
                "battery_percent": robot.battery_percent,
                "current_task_id": robot.task_id,
                "last_seen_at": self.snapshot.last_updated,
            }
            for robot in self.snapshot.robots
        ]

    def _timeline_rows(self) -> list[dict]:
        return [
            {
                "occurred_at": event.occurred_at,
                "task_id": event.task_id,
                "event_type": event.title,
                "message": event.detail,
            }
            for event in self.snapshot.timeline
        ]


class PresentationTaskMonitorPage(TaskMonitorPage):
    def __init__(self, *, autostart_stream=True):
        super().__init__(autostart_stream=False)
        self.consumer_id = "ui-presentation-admin-demo"
        if autostart_stream:
            self._start_snapshot_load()

    def apply_snapshot(self, snapshot):
        super().apply_snapshot(translate_robot_display_payload(snapshot))

    def apply_stream_event(self, event):
        super().apply_stream_event(translate_robot_display_payload(event))


class PresentationAlertsLogPage(AlertLogPage):
    def __init__(self, *, autoload: bool = True):
        super().__init__(autoload=autoload)
        self.robot_id_input.setPlaceholderText("예: ROPI 2")

    def _collect_filters(self):
        filters = super()._collect_filters()
        filters["robot_id"] = runtime_robot_id_for_display(filters.get("robot_id"))
        return filters

    def apply_alert_log_bundle(self, bundle):
        super().apply_alert_log_bundle(translate_robot_display_payload(bundle))


class PresentationAdminDemoWindow(QMainWindow):
    NAV_ITEMS = [
        ("home", "홈"),
        ("task_request", "작업 요청"),
        ("task_monitor", "작업 모니터"),
        ("alerts", "알림/로그"),
    ]

    def __init__(
        self,
        store: DemoAdminStore | None = None,
        *,
        autostart_runtime: bool = True,
    ):
        super().__init__()
        self.store = store or DemoAdminStore(build_admin_demo_snapshot())
        self.setWindowTitle("ROPI 관제 콘솔")
        self.setMinimumSize(1280, 800)

        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.admin_shell = AdminShell(
            nav_items=self.NAV_ITEMS,
            user_name="관제 운영자",
            user_role="관제 운영자",
            on_logout=None,
        )
        self.home_page = PresentationHomePage(self.store)
        self.request_page = TaskRequestPage()
        self.monitor_page = PresentationTaskMonitorPage(
            autostart_stream=autostart_runtime
        )
        self.alerts_page = PresentationAlertsLogPage(autoload=autostart_runtime)
        self.map_widget = self.home_page.map_widget

        self.admin_shell.add_page("home", self.home_page)
        self.admin_shell.add_page("task_request", self.request_page)
        self.admin_shell.add_page("task_monitor", self.monitor_page)
        self.admin_shell.add_page("alerts", self.alerts_page)
        self.admin_shell.set_page("home")
        self.admin_shell.nav_requested.connect(self.admin_shell.set_page)
        self.store.subscribe(self._refresh_pages)
        layout.addWidget(self.admin_shell)

    def _refresh_pages(self, snapshot: DemoSnapshot) -> None:
        self.home_page.refresh_from_store(snapshot)

    def closeEvent(self, event):
        for page in (self.request_page, self.monitor_page, self.alerts_page):
            shutdown = getattr(page, "shutdown", None)
            if callable(shutdown):
                shutdown()
        super().closeEvent(event)


def create_demo_window(*, autostart_runtime: bool = True) -> PresentationAdminDemoWindow:
    return PresentationAdminDemoWindow(autostart_runtime=autostart_runtime)


def show_demo_window(window: QMainWindow) -> None:
    window.showMaximized()


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())

    smoke = "--smoke" in args
    window = create_demo_window(autostart_runtime=not smoke)
    if smoke:
        window.ensurePolished()
        window.close()
        return

    show_demo_window(window)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
