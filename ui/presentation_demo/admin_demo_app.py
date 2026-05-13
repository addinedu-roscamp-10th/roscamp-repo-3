from __future__ import annotations

import math
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QPen,
    QPolygonF,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.presentation_demo.admin_demo_data import (
    DemoAdminStore,
    DemoMapMarker,
    DemoSnapshot,
    DemoTask,
    build_alert_log_capture_bundle,
    build_admin_demo_snapshot,
    build_task_monitor_slide_snapshot,
    display_status,
)
from ui.presentation_demo.robot_display import (
    runtime_robot_id_for_display,
    translate_robot_display_text,
    translate_robot_display_payload,
)
from ui.utils.core.styles import load_stylesheet
from ui.utils.pages.caregiver.alert_log_page import AlertLogPage
from ui.utils.pages.caregiver.home_dashboard_page import CaregiverHomePage
from ui.utils.pages.caregiver.task_monitor_page import FallEvidenceImageDialog
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
DEMO_MAP_CANVAS_SIZE = (600, 337)
DEMO_MAP_FLOW_CARD_HEIGHT = DEMO_MAP_CANVAS_SIZE[1] + 72


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
    marker_label_width_px = 92
    marker_label_height_px = 40
    marker_name_font_size_pt = 9
    marker_detail_font_size_pt = 8

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
        name_font.setPointSize(self.marker_name_font_size_pt)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(QColor("#16202A"))
        painter.drawText(
            label_rect.adjusted(7, 3, -7, -21),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            marker.display_id,
        )

        detail_font = QFont()
        detail_font.setPointSize(self.marker_detail_font_size_pt)
        detail_font.setBold(True)
        painter.setFont(detail_font)
        painter.setPen(color.darker(115))
        painter.drawText(
            label_rect.adjusted(7, 20, -7, -3),
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
        self.setMinimumWidth(320)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.setFixedHeight(DEMO_MAP_FLOW_CARD_HEIGHT)

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
        self.presentation_map_card = None
        self.presentation_map_flow_row = None
        self._detached_production_home_widgets = []
        super().__init__(autoload=False, auto_system_status_poll=False)
        self._detach_production_map_flow_row()
        self._insert_map_flow_row()
        self._apply_presentation_home_text_scale()
        self.refresh_from_store(store.snapshot)

    def _detach_production_map_flow_row(self) -> None:
        page_layout = self.layout()
        for frame in self.findChildren(QFrame, "homeMapFlowRow"):
            if page_layout is not None:
                page_layout.removeWidget(frame)
            frame.hide()
            frame.setParent(None)
            self._detached_production_home_widgets.append(frame)

    def _insert_map_flow_row(self) -> None:
        row = QFrame()
        row.setObjectName("presentationMapFlowRow")
        row.setProperty("presentation_map_flow_row", True)
        self.presentation_map_flow_row = row
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(16)

        map_card = QFrame()
        map_card.setObjectName("card")
        map_card.setProperty("presentation_home_map", True)
        map_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        map_card.setFixedHeight(DEMO_MAP_FLOW_CARD_HEIGHT)
        self.presentation_map_card = map_card
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
            1,
            Qt.AlignmentFlag.AlignTop,
        )
        row_layout.addWidget(self.compact_flow_card, 1, Qt.AlignmentFlag.AlignTop)
        row_layout.setStretch(0, 1)
        row_layout.setStretch(1, 1)

        self.layout().insertWidget(3, row)

        flow_wrap = self.flow_scroll.parentWidget()
        if flow_wrap is not None:
            flow_wrap.hide()

    def _apply_presentation_home_text_scale(self) -> None:
        self.setObjectName("presentationHomePage")
        self.setStyleSheet(
            """
            QWidget#presentationHomePage QLabel#homeKpiTitle {
                font-size: 16px;
                font-weight: 800;
            }
            QWidget#presentationHomePage QLabel#homeKpiHint,
            QWidget#presentationHomePage QLabel#mutedText {
                font-size: 15px;
                font-weight: 700;
            }
            QWidget#presentationHomePage QLabel#homeRobotTitle,
            QWidget#presentationHomePage QLabel#homeTaskTitle {
                font-size: 18px;
                font-weight: 900;
            }
            QWidget#presentationHomePage QLabel#homeRobotFieldKey,
            QWidget#presentationHomePage QLabel#homeTaskFieldKey {
                font-size: 14px;
                font-weight: 800;
            }
            QWidget#presentationHomePage QLabel#homeRobotFieldValue,
            QWidget#presentationHomePage QLabel#homeTaskFieldValue,
            QWidget#presentationHomePage QLabel#homeTaskFieldDetail {
                font-size: 16px;
                font-weight: 800;
            }
            """
        )

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


class PresentationFallEvidenceImageDialog(FallEvidenceImageDialog):
    DETECTION_CLASS_LABELS = {
        "fall": "낙상",
        "person": "사람",
        "object": "객체",
    }

    def _format_detections(self):
        detections = self.response.get("detections")
        if not isinstance(detections, list) or not detections:
            return "감지 영역 없음"

        parts = []
        for detection in detections:
            if not isinstance(detection, dict):
                continue
            class_name = self._display_detection_class(
                detection.get("class_name") or detection.get("label") or "object"
            )
            confidence = detection.get("confidence")
            if confidence is None:
                parts.append(class_name)
            else:
                try:
                    parts.append(f"{class_name} {float(confidence):.2f}")
                except (TypeError, ValueError):
                    parts.append(class_name)
        return ", ".join(parts) or "감지 영역 없음"

    @classmethod
    def _display_detection_class(cls, value) -> str:
        text = str(value or "").strip()
        if not text:
            text = "object"
        return cls.DETECTION_CLASS_LABELS.get(
            text.lower(),
            translate_robot_display_text(text),
        )


class PresentationTaskMonitorPage(QWidget):
    def __init__(self, *, autostart_stream: bool = False):
        super().__init__()
        self.snapshot = build_task_monitor_slide_snapshot()
        self.selected_task_id = self.snapshot.selected_task_id
        self.current_step_index = self.snapshot.current_step_index
        self.step_frames: list[QFrame] = []
        self.step_current_labels: list[QLabel] = []
        self.current_phase_value_label = None
        self.latest_feedback_value_label = None
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(1000)
        self.progress_timer.timeout.connect(self._advance_delivery_progress_animation)
        self.setObjectName("presentationTaskMonitorPage")
        self._build_ui()
        self._apply_lifecycle_step_state(update_task_text=False)
        self._apply_slide_style()

    def _create_fall_evidence_dialog(self, response):
        dialog = PresentationFallEvidenceImageDialog(response=response, parent=self)
        translate_widget_texts(dialog)
        return dialog

    def shutdown(self) -> None:
        self.progress_timer.stop()
        return

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        header_row = QHBoxLayout()
        header_row.setSpacing(16)
        self.header = PageHeader(
            "작업 모니터",
            "선택 작업의 진행 단계와 최근 피드백을 한눈에 확인합니다.",
            statuses={
                "발표 화면": "online",
                "데모 데이터": "online",
            },
            show_status=True,
        )
        self.time_card = PageTimeCard(status_text="발표용 작업 스냅샷")
        self.time_card.mark_updated("slide")
        header_row.addWidget(self.header, 1)
        header_row.addWidget(self.time_card, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header_row)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(12)
        for title, value, tone in (
            ("진행 작업", "3", "green"),
            ("주의 필요", "1", "amber"),
            ("완료 작업", "1", "blue"),
        ):
            summary_row.addWidget(
                self._build_summary_card(title, value, tone),
                1,
            )
        root.addLayout(summary_row)

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(self._build_task_list_card(), 5)
        body.addWidget(self._build_detail_card(), 4)
        root.addLayout(body, 1)

    def _build_summary_card(self, title: str, value: str, tone: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setProperty("presentation_monitor_summary", tone)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("mutedText")
        value_label = QLabel(value)
        value_label.setObjectName("presentationMonitorSummaryValue")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card

    def _build_task_list_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setProperty("presentation_monitor_list", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        title = QLabel("작업 목록")
        title.setObjectName("sectionTitle")
        hint = QLabel("운반 · 순찰 · 안내")
        hint.setObjectName("mutedText")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(hint)
        layout.addLayout(title_row)

        self.task_table = QTableWidget(len(self.snapshot.rows), 6)
        self.task_table.setObjectName("presentationTaskTable")
        self.task_table.setHorizontalHeaderLabels(
            ["상태", "작업", "유형", "담당 ROPI", "현재 단계", "업데이트"]
        )
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.task_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.task_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setShowGrid(False)
        self.task_table.horizontalHeader().setStretchLastSection(True)

        for row_index, row in enumerate(self.snapshot.rows):
            values = (
                row.status,
                row.title,
                row.task_type,
                row.robot_display_id,
                row.phase,
                row.updated_at,
            )
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                )
                if column_index in {0, 2, 3, 5}:
                    item.setTextAlignment(
                        int(
                            Qt.AlignmentFlag.AlignCenter
                            | Qt.AlignmentFlag.AlignVCenter
                        )
                    )
                self.task_table.setItem(row_index, column_index, item)
            self.task_table.setRowHeight(row_index, 54)

        self.task_table.selectRow(0)
        self.task_table.setColumnWidth(0, 96)
        self.task_table.setColumnWidth(1, 170)
        self.task_table.setColumnWidth(2, 72)
        self.task_table.setColumnWidth(3, 90)
        self.task_table.setColumnWidth(4, 128)
        self.task_table.setMinimumHeight(300)
        self.task_table.cellClicked.connect(self._handle_task_row_clicked)
        layout.addWidget(self.task_table, 1)
        return card

    def _build_detail_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setProperty("presentation_monitor_detail", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(16)

        title_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(6)
        eyebrow = QLabel("선택 작업")
        eyebrow.setObjectName("mutedText")
        selected_title = QLabel(self.snapshot.selected_title)
        selected_title.setObjectName("presentationMonitorHeroTitle")
        title_box.addWidget(eyebrow)
        title_box.addWidget(selected_title)
        title_row.addLayout(title_box, 1)
        title_row.addWidget(StatusChip("진행 중", "green"), 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(title_row)

        detail_grid = QGridLayout()
        detail_grid.setContentsMargins(0, 0, 0, 0)
        detail_grid.setHorizontalSpacing(10)
        detail_grid.setVerticalSpacing(10)
        detail_items = (
            ("작업 유형", self.snapshot.selected_task_type),
            ("담당 로봇", self.snapshot.selected_robot),
            ("목적지", self.snapshot.selected_destination),
            ("현재 단계", self.snapshot.selected_phase),
            ("최근 피드백", self.snapshot.latest_feedback),
        )
        for index, (key, value) in enumerate(detail_items):
            detail_grid.addWidget(
                self._build_detail_box(key, value),
                index // 2,
                index % 2,
            )
        layout.addLayout(detail_grid)

        timeline_title = QLabel("운반 진행 단계")
        timeline_title.setObjectName("sectionTitle")
        layout.addWidget(timeline_title)
        layout.addLayout(self._build_lifecycle_timeline())

        layout.addStretch(1)
        return card

    def _build_detail_box(self, key: str, value: str) -> QFrame:
        box = QFrame()
        box.setObjectName("infoBox")
        box.setProperty("presentation_detail_box", True)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)
        key_label = QLabel(key)
        key_label.setObjectName("mutedText")
        value_label = QLabel(value)
        value_label.setObjectName("presentationMonitorDetailValue")
        value_label.setWordWrap(True)
        if key == "현재 단계":
            self.current_phase_value_label = value_label
        elif key == "최근 피드백":
            self.latest_feedback_value_label = value_label
        layout.addWidget(key_label)
        layout.addWidget(value_label)
        return box

    def _build_lifecycle_timeline(self) -> QHBoxLayout:
        timeline = QHBoxLayout()
        self.step_frames = []
        self.step_current_labels = []
        timeline.setSpacing(8)
        for index, step in enumerate(self.snapshot.lifecycle_steps):
            step_box = QFrame()
            step_box.setObjectName("presentationMonitorStep")
            step_box.setProperty("current", False)
            step_box.setProperty("completed", False)
            step_layout = QVBoxLayout(step_box)
            step_layout.setContentsMargins(10, 10, 10, 10)
            step_layout.setSpacing(4)

            marker = QLabel("●")
            marker.setObjectName("presentationMonitorStepMarker")
            marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel(step)
            label.setObjectName("presentationMonitorStepLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            current = QLabel("현재" if index == self.snapshot.current_step_index else " ")
            current.setObjectName("presentationMonitorStepCurrent")
            current.setAlignment(Qt.AlignmentFlag.AlignCenter)

            step_layout.addWidget(marker)
            step_layout.addWidget(label)
            step_layout.addWidget(current)
            timeline.addWidget(step_box, 1)
            self.step_frames.append(step_box)
            self.step_current_labels.append(current)
        return timeline

    def _handle_task_row_clicked(self, row: int, column: int) -> None:
        if row < 0 or row >= len(self.snapshot.rows):
            return
        selected_row = self.snapshot.rows[row]
        self.selected_task_id = selected_row.task_id
        if selected_row.task_id == self.snapshot.selected_task_id:
            self.start_delivery_progress_animation()

    def start_delivery_progress_animation(self) -> None:
        self.progress_timer.stop()
        self.current_step_index = 0
        self._apply_lifecycle_step_state()
        if len(self.snapshot.lifecycle_steps) > 1:
            self.progress_timer.start()

    def _advance_delivery_progress_animation(self) -> None:
        last_index = len(self.snapshot.lifecycle_steps) - 1
        if self.current_step_index < last_index:
            self.current_step_index += 1
            self._apply_lifecycle_step_state()
        if self.current_step_index >= last_index:
            self.progress_timer.stop()

    def _apply_lifecycle_step_state(self, *, update_task_text: bool = True) -> None:
        if not self.snapshot.lifecycle_steps:
            return
        last_index = len(self.snapshot.lifecycle_steps) - 1
        self.current_step_index = max(0, min(self.current_step_index, last_index))
        current_step = self.snapshot.lifecycle_steps[self.current_step_index]

        if update_task_text:
            selected_progress = self._selected_row_progress_for()
            if self.current_phase_value_label is not None:
                self.current_phase_value_label.setText(current_step)
            if self.latest_feedback_value_label is not None:
                self.latest_feedback_value_label.setText(selected_progress.feedback)
            self._apply_task_table_progress(0, selected_progress)
            for update in self.snapshot.sparse_row_updates:
                if update.step_index == self.current_step_index:
                    self._apply_task_table_progress(update.row_index, update.progress)

        for index, step_frame in enumerate(self.step_frames):
            is_current = index == self.current_step_index
            is_completed = index < self.current_step_index
            step_frame.setProperty("current", is_current)
            step_frame.setProperty("completed", is_completed)
            if index < len(self.step_current_labels):
                self.step_current_labels[index].setText("현재" if is_current else " ")
            style = step_frame.style()
            style.unpolish(step_frame)
            style.polish(step_frame)
            step_frame.update()

    def _selected_row_progress_for(self):
        progress_steps = self.snapshot.selected_row_progress
        progress_index = min(self.current_step_index, len(progress_steps) - 1)
        return progress_steps[progress_index]

    def _apply_task_table_progress(self, row_index: int, progress) -> None:
        self._set_task_table_text(row_index, 0, progress.status)
        self._set_task_table_text(row_index, 4, progress.phase)
        self._set_task_table_text(row_index, 5, progress.updated_at)

    def _set_task_table_text(self, row_index: int, column_index: int, text: str) -> None:
        item = self.task_table.item(row_index, column_index)
        if item is not None:
            item.setText(text)

    def _apply_slide_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#presentationTaskMonitorPage QLabel#presentationMonitorSummaryValue {
                color: #0F172A;
                font-size: 30px;
                font-weight: 900;
            }
            QWidget#presentationTaskMonitorPage QLabel#presentationMonitorHeroTitle {
                color: #0F172A;
                font-size: 28px;
                font-weight: 900;
            }
            QWidget#presentationTaskMonitorPage QLabel#presentationMonitorDetailValue {
                color: #111827;
                font-size: 17px;
                font-weight: 800;
            }
            QWidget#presentationTaskMonitorPage QTableWidget#presentationTaskTable {
                font-size: 15px;
                font-weight: 700;
                selection-background-color: #DBEAFE;
                selection-color: #0F172A;
            }
            QWidget#presentationTaskMonitorPage QHeaderView::section {
                font-size: 14px;
                font-weight: 800;
                padding: 8px;
            }
            QWidget#presentationTaskMonitorPage QFrame#presentationMonitorStep {
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                background: #F8FAFC;
            }
            QWidget#presentationTaskMonitorPage QFrame#presentationMonitorStep[completed="true"] {
                border: 1px solid #93C5FD;
                background: #EFF6FF;
            }
            QWidget#presentationTaskMonitorPage QFrame#presentationMonitorStep[current="true"] {
                border: 2px solid #16A34A;
                background: #ECFDF5;
            }
            QWidget#presentationTaskMonitorPage QLabel#presentationMonitorStepMarker {
                color: #94A3B8;
                font-size: 18px;
                font-weight: 900;
            }
            QWidget#presentationTaskMonitorPage QLabel#presentationMonitorStepLabel {
                color: #0F172A;
                font-size: 14px;
                font-weight: 800;
            }
            QWidget#presentationTaskMonitorPage QLabel#presentationMonitorStepCurrent {
                color: #16A34A;
                font-size: 13px;
                font-weight: 900;
            }
            """
        )


class PresentationAlertsLogPage(AlertLogPage):
    def __init__(
        self,
        *,
        autoload: bool = True,
        use_capture_bundle: bool = True,
    ):
        super().__init__(autoload=autoload and not use_capture_bundle)
        self.use_capture_bundle = use_capture_bundle
        self.robot_id_input.setPlaceholderText("예: ROPI 2")
        self.source_input.setPlaceholderText("예: 관제 서버")
        self.event_type_input.setPlaceholderText("예: 낙상 의심 감지")
        self.payload_label.setText("상세\n내용")
        self.table.setHorizontalHeaderLabels(
            [
                "이벤트 번호",
                "발생 시각",
                "심각도",
                "출처",
                "작업 번호",
                "로봇",
                "이벤트",
                "메시지",
            ]
        )
        for index in range(self.severity_combo.count()):
            value = self.severity_combo.itemData(index)
            if value:
                self.severity_combo.setItemText(
                    index,
                    translate_robot_display_text(str(value)),
                )
        translate_widget_texts(self)
        if self.use_capture_bundle:
            self.apply_alert_log_bundle(build_alert_log_capture_bundle())

    def _collect_filters(self):
        filters = super()._collect_filters()
        filters["robot_id"] = runtime_robot_id_for_display(filters.get("robot_id"))
        return filters

    def apply_alert_log_bundle(self, bundle):
        super().apply_alert_log_bundle(translate_robot_display_payload(bundle))
        if self.events:
            self.table.selectRow(0)
        translate_widget_texts(self)

    def _render_detail(self, event):
        payload = event.get("payload") if isinstance(event, dict) else None
        location = event.get("location") or self._payload_value(payload, "위치")
        reason_label = (
            "확인 필요 사유"
            if event.get("result_code") == "확인 필요"
            else "처리 사유"
        )
        detail_rows = [
            ("이벤트 번호", self._event_value(event, "event_id")),
            ("발생 시각", self._event_value(event, "occurred_at")),
            ("심각도", self._event_value(event, "severity")),
            ("출처", self._event_value(event, "source_component")),
            ("이벤트", self._event_value(event, "event_type")),
            ("작업 번호", self._event_value(event, "task_id")),
            ("담당 ROPI", self._event_value(event, "robot_id")),
            ("위치", self._display_value(location)),
            ("처리 상태", self._event_value(event, "result_code")),
            (reason_label, self._event_value(event, "reason_code")),
            ("메시지", self._event_value(event, "message")),
        ]
        self.detail_list.set_rows(detail_rows)
        self._render_payload(payload)
        self.related_list.set_rows(
            [
                ("작업 번호", self._event_value(event, "task_id")),
                ("로봇", self._event_value(event, "robot_id")),
            ]
        )
        self._sync_related_actions(event)

    @staticmethod
    def _display_value(value) -> str:
        if value is None or value == "":
            return "-"
        return str(value)

    def _event_value(self, event, key: str) -> str:
        if not isinstance(event, dict):
            return "-"
        return self._display_value(event.get(key))

    def _payload_value(self, payload, key: str):
        if not isinstance(payload, dict):
            return None
        return payload.get(key) or payload.get(translate_robot_display_text(key))


def translate_widget_texts(widget: QWidget) -> None:
    for label in widget.findChildren(QLabel):
        label.setText(translate_robot_display_text(label.text()))

    for button in widget.findChildren(QPushButton):
        button.setText(translate_robot_display_text(button.text()))

    for text_edit in widget.findChildren(QPlainTextEdit):
        text_edit.setPlainText(translate_robot_display_text(text_edit.toPlainText()))

    for table in widget.findChildren(QTableWidget):
        for column in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setText(translate_robot_display_text(header_item.text()))
        for row in range(table.rowCount()):
            for column in range(table.columnCount()):
                item = table.item(row, column)
                if item is not None:
                    item.setText(translate_robot_display_text(item.text()))


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
        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.activated.connect(self.toggle_fullscreen)

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
        self._hide_task_request_follow_tab()
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

    def _hide_task_request_follow_tab(self) -> None:
        follow_btn = getattr(self.request_page, "follow_btn", None)
        if follow_btn is None:
            return
        follow_btn.setText("")
        follow_btn.setHidden(True)

    def toggle_fullscreen(self) -> None:
        if self.windowState() & Qt.WindowState.WindowFullScreen:
            self.showMaximized()
            return
        self.showFullScreen()

    def closeEvent(self, event):
        self._shutdown_request_page_background_work()
        for page in (self.request_page, self.monitor_page, self.alerts_page):
            shutdown = getattr(page, "shutdown", None)
            if callable(shutdown):
                shutdown()
        super().closeEvent(event)

    def _shutdown_request_page_background_work(self) -> None:
        for form in getattr(self.request_page, "forms", []):
            if hasattr(form, "LOAD_STATE_LOADED"):
                form._items_load_state = form.LOAD_STATE_LOADED
            stop_workers = getattr(form, "_stop_worker_threads", None)
            if callable(stop_workers):
                stop_workers()
            stop_submit = getattr(form, "_stop_submit_thread", None)
            if callable(stop_submit):
                stop_submit()


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
