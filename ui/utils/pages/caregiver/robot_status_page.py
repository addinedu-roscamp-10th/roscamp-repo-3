from __future__ import annotations

import base64
import binascii
import math
import re

from PyQt6.QtCore import QPointF
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.utils.core.worker_threads import start_worker_thread, stop_worker_thread
from ui.utils.network.service_clients import (
    CaregiverRemoteService,
    CoordinateConfigRemoteService,
)
from ui.utils.widgets.admin_common import (
    KeyValueList,
    KeyValueRow,
    StatusChip,
    SummaryCard,
    battery_text as _battery_text,
    display_text as _display,
    operator_datetime_text as _datetime,
)
from ui.utils.widgets.admin_shell import PageHeader, PageTimeCard
from ui.utils.widgets.map_canvas import MapCanvasWidget


SUMMARY_ITEMS = (
    ("total_robot_count", "전체 로봇"),
    ("online_robot_count", "온라인"),
    ("offline_robot_count", "오프라인"),
    ("caution_robot_count", "주의"),
)

TABLE_HEADERS = [
    "로봇 ID",
    "표시명",
    "구분",
    "지원 기능",
    "연결",
    "상태",
    "배터리",
    "현재 작업",
    "마지막 수신",
]


def _chip_type(connection_status: str) -> str:
    normalized = str(connection_status or "").upper()
    if normalized == "ONLINE":
        return "green"
    if normalized == "DEGRADED":
        return "yellow"
    if normalized == "OFFLINE":
        return "red"
    return "blue"


def _capabilities_text(capabilities) -> str:
    if isinstance(capabilities, (list, tuple)):
        values = [str(item).strip() for item in capabilities if str(item).strip()]
        return ", ".join(values) if values else "-"
    return _display(capabilities)


def _is_ok_response(response):
    return isinstance(response, dict) and response.get("result_code", "OK") == "OK"


def _format_response_error(response, default_message):
    response = response if isinstance(response, dict) else {}
    return str(response.get("result_message") or response.get("reason_code") or default_message)


def _decode_base64_asset(value):
    try:
        return base64.b64decode(str(value or "").encode("ascii"), validate=True)
    except (binascii.Error, ValueError):
        return b""


def _selected_map_id(*, preferred_map_id, map_profiles, robots):
    map_ids = [
        str(profile.get("map_id") or "").strip()
        for profile in map_profiles or []
        if isinstance(profile, dict) and str(profile.get("map_id") or "").strip()
    ]
    preferred_map_id = str(preferred_map_id or "").strip()
    if preferred_map_id and preferred_map_id in map_ids:
        return preferred_map_id

    robot_map_counts = {}
    for robot in robots or []:
        pose = robot.get("current_pose") if isinstance(robot, dict) else None
        if not isinstance(pose, dict):
            continue
        map_id = str(pose.get("map_id") or "").strip()
        if map_id and map_id in map_ids:
            robot_map_counts[map_id] = robot_map_counts.get(map_id, 0) + 1
    if robot_map_counts:
        return sorted(robot_map_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    for profile in map_profiles or []:
        if not isinstance(profile, dict):
            continue
        if bool(profile.get("is_active")):
            return str(profile.get("map_id") or "").strip()
    return map_ids[0] if map_ids else None


def _optional_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _robot_display_sort_key(robot: dict):
    robot_id = str(robot.get("robot_id") or "").strip().lower()
    robot_type = str(robot.get("robot_type") or "").strip().upper()
    prefix_rank = 1
    if robot_id.startswith("pinky") or robot_type == "MOBILE":
        prefix_rank = 0
    elif robot_id.startswith("jetcobot") or robot_type == "ARM":
        prefix_rank = 1

    return (prefix_rank, _natural_robot_id_key(robot_id), robot_id)


def _natural_robot_id_key(robot_id: str):
    parts = re.split(r"(\d+)", robot_id)
    return [int(part) if part.isdigit() else part for part in parts]


class RobotStatusLoadWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, *, selected_map_id=None):
        super().__init__()
        self.selected_map_id = str(selected_map_id or "").strip() or None

    def run(self):
        try:
            bundle = CaregiverRemoteService().get_robot_status_bundle() or {}
            self._attach_map_payload(bundle)
            self.finished.emit(True, bundle)
        except Exception as exc:
            self.finished.emit(False, str(exc))

    def _attach_map_payload(self, bundle):
        bundle = bundle if isinstance(bundle, dict) else {}
        try:
            service = CoordinateConfigRemoteService()
            profiles_response = service.list_map_profiles()
            if not _is_ok_response(profiles_response):
                bundle["map_asset_error"] = _format_response_error(
                    profiles_response,
                    "맵 목록을 불러오지 못했습니다.",
                )
                return

            profiles = [
                profile
                for profile in profiles_response.get("map_profiles") or []
                if isinstance(profile, dict)
            ]
            bundle["map_profiles"] = profiles
            selected_map_id = _selected_map_id(
                preferred_map_id=self.selected_map_id,
                map_profiles=profiles,
                robots=bundle.get("robots") or [],
            )
            bundle["selected_map_id"] = selected_map_id
            if not selected_map_id:
                return

            yaml_asset = service.get_map_asset(
                asset_type="YAML",
                map_id=selected_map_id,
                encoding="TEXT",
            )
            if not _is_ok_response(yaml_asset):
                bundle["map_asset_error"] = _format_response_error(
                    yaml_asset,
                    "맵 YAML을 불러오지 못했습니다.",
                )
                return

            pgm_asset = service.get_map_asset(
                asset_type="PGM",
                map_id=selected_map_id,
                encoding="BASE64",
            )
            if not _is_ok_response(pgm_asset):
                bundle["map_asset_error"] = _format_response_error(
                    pgm_asset,
                    "맵 PGM을 불러오지 못했습니다.",
                )
                return

            bundle["map_assets"] = {
                "map_id": selected_map_id,
                "yaml_text": str(yaml_asset.get("content_text") or ""),
                "pgm_bytes": _decode_base64_asset(pgm_asset.get("content_base64")),
                "yaml_sha256": yaml_asset.get("sha256"),
                "pgm_sha256": pgm_asset.get("sha256"),
            }
        except Exception as exc:
            bundle["map_asset_error"] = str(exc)


class RobotLocationMapCanvas(MapCanvasWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("robotLocationMapCanvas")
        self.visible_robot_ids = []
        self.robot_markers = []

    def show_robots(self, robots, *, selected_map_id):
        self.visible_robot_ids = []
        self.robot_markers = []
        selected_map_id = str(selected_map_id or "").strip()
        if not self.map_loaded or not selected_map_id:
            self.update()
            return

        for robot in robots or []:
            if not isinstance(robot, dict):
                continue
            pose = robot.get("current_pose")
            if not isinstance(pose, dict):
                continue
            if str(pose.get("map_id") or "").strip() != selected_map_id:
                continue
            point = self.world_to_pixel(
                {
                    "x": pose.get("x"),
                    "y": pose.get("y"),
                }
            )
            if point is None:
                continue
            robot_id = _display(robot.get("robot_id"))
            self.visible_robot_ids.append(robot_id)
            self.robot_markers.append(
                {
                    "robot_id": robot_id,
                    "pixel": point,
                    "yaw": _optional_float(pose.get("yaw"), default=0.0),
                    "connection_status": str(
                        robot.get("connection_status") or ""
                    ).upper(),
                }
            )
        self.update()

    def draw_overlay(self, painter, target):
        for marker in self.robot_markers:
            point = self.to_view_point(marker.get("pixel"), target)
            if point is None:
                continue
            status = marker.get("connection_status")
            fill = QColor("#2563EB" if status == "ONLINE" else "#F59E0B")
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.setBrush(fill)
            painter.drawEllipse(point, 8, 8)

            yaw = marker.get("yaw")
            if yaw is not None:
                heading = QPointF(
                    point.x() + math.cos(float(yaw)) * 18.0,
                    point.y() - math.sin(float(yaw)) * 18.0,
                )
                painter.setPen(QPen(QColor("#1D4ED8"), 2))
                painter.drawLine(point, heading)

            painter.setPen(QPen(QColor("#111827"), 1))
            painter.drawText(point + QPointF(10, -10), marker.get("robot_id") or "-")


class RobotStatusCard(QFrame):
    def __init__(self, robot: dict):
        super().__init__()
        self.robot_id = robot.get("robot_id")
        self.setObjectName("robotStatusCard")
        self.setProperty(
            "connection_status",
            str(robot.get("connection_status") or "").lower(),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title_row = QHBoxLayout()
        name = QLabel(_display(robot.get("robot_id")))
        name.setObjectName("sectionTitle")
        chip = StatusChip(
            _display(robot.get("connection_status")),
            _chip_type(robot.get("connection_status")),
        )
        title_row.addWidget(name)
        title_row.addStretch()
        title_row.addWidget(chip)

        details = [
            ("구분", _display(robot.get("robot_type"))),
            ("지원 기능", _capabilities_text(robot.get("capabilities"))),
            ("현재 작업", _display(robot.get("current_task_id"))),
            ("단계", _display(robot.get("current_phase"))),
            ("위치", _display(robot.get("current_location"))),
            ("배터리", _battery_text(robot.get("battery_percent"))),
            ("마지막 수신", _datetime(robot.get("last_seen_at"))),
        ]

        layout.addLayout(title_row)
        for key, value in details:
            layout.addWidget(KeyValueRow(key, value))


class RobotStatusPage(QWidget):
    def __init__(self, *, autoload: bool = True):
        super().__init__()
        self._worker_stop_wait_ms = 1000
        self.load_thread = None
        self.load_worker = None
        self.summary_cards = {}
        self.robots = []
        self.map_profiles = []
        self.selected_map_id = None
        self._syncing_map_selector = False

        self._build_ui()
        if autoload:
            self.refresh_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        header_row = QHBoxLayout()
        header_row.setSpacing(16)
        header_row.addWidget(
            PageHeader(
                "로봇 상태",
                "로봇별 연결 상태, 작업, 배터리, 위치, 최근 수신 시각을 확인합니다.",
            ),
            1,
        )

        self.time_card = PageTimeCard(
            refresh_text="새로고침",
            refresh_property=("robot_status_action", "refresh"),
            on_refresh=self.refresh_data,
        )
        self.refresh_button = self.time_card.refresh_button
        self.last_update_label = self.time_card.last_update_label
        self.status_label = self.time_card.status_label
        header_row.addWidget(self.time_card)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(16)
        for key, title in SUMMARY_ITEMS:
            card = SummaryCard(title, initial_value="0대")
            self.summary_cards[key] = card
            summary_row.addWidget(card)

        self.card_grid = QGridLayout()
        self.card_grid.setHorizontalSpacing(16)
        self.card_grid.setVerticalSpacing(16)

        cards_wrap = QFrame()
        cards_wrap.setObjectName("robotCardsPanel")
        self.robot_cards_panel = cards_wrap
        cards_layout = QVBoxLayout(cards_wrap)
        cards_layout.setContentsMargins(20, 20, 20, 20)
        cards_layout.setSpacing(14)
        cards_title = QLabel("로봇 카드")
        cards_title.setObjectName("sectionTitle")
        cards_layout.addWidget(cards_title)
        self.location_panel = QFrame()
        self.location_panel.setObjectName("robotLocationMapPanel")
        self.location_panel.setMinimumHeight(320)
        location_layout = QVBoxLayout(self.location_panel)
        location_layout.setContentsMargins(18, 18, 18, 18)
        location_layout.setSpacing(12)
        location_header = QHBoxLayout()
        location_title = QLabel("로봇 위치 맵")
        location_title.setObjectName("sectionTitle")
        self.map_selector = QComboBox()
        self.map_selector.setObjectName("robotMapSelector")
        self.map_selector.currentIndexChanged.connect(self._handle_map_selection_changed)
        location_header.addWidget(location_title)
        location_header.addStretch()
        location_header.addWidget(self.map_selector)
        self.robot_map_canvas = RobotLocationMapCanvas()
        self.robot_map_canvas.setMinimumHeight(280)
        self.map_status_label = QLabel("맵을 불러오지 않았습니다.")
        self.map_status_label.setObjectName("mutedText")
        self.map_status_label.setWordWrap(True)
        location_layout.addLayout(location_header)
        location_layout.addWidget(self.robot_map_canvas, 1)
        location_layout.addWidget(self.map_status_label)
        cards_layout.addWidget(self.location_panel)
        cards_layout.addLayout(self.card_grid)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(18)

        table_card = QFrame()
        table_card.setObjectName("formCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(20, 20, 20, 20)
        table_layout.setSpacing(12)
        table_title = QLabel("로봇 상세 목록")
        table_title.setObjectName("sectionTitle")

        self.table = QTableWidget(0, len(TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._handle_table_selection)

        table_layout.addWidget(table_title)
        table_layout.addWidget(self.table)

        side_column = QVBoxLayout()
        side_column.setSpacing(18)

        detail_card = QFrame()
        detail_card.setObjectName("formCard")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(20, 20, 20, 20)
        detail_layout.setSpacing(10)
        detail_title = QLabel("로봇 상세")
        detail_title.setObjectName("sectionTitle")
        self.detail_list = KeyValueList("테이블에서 로봇을 선택하세요.")
        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(self.detail_list)

        composition_card = QFrame()
        composition_card.setObjectName("noticeCard")
        composition_layout = QVBoxLayout(composition_card)
        composition_layout.setContentsMargins(20, 20, 20, 20)
        composition_layout.setSpacing(8)
        composition_title = QLabel("운반 복합 로봇 구성")
        composition_title.setObjectName("sectionTitle")
        self.composition_rows = []
        composition_layout.addWidget(composition_title)

        side_column.addWidget(detail_card)
        side_column.addWidget(composition_card)
        side_column.addStretch()

        self.composition_layout = composition_layout
        bottom_row.addWidget(table_card, 2)
        bottom_row.addLayout(side_column, 1)

        root.addLayout(header_row)
        root.addLayout(summary_row)
        root.addWidget(cards_wrap)
        root.addLayout(bottom_row, 1)

    def refresh_data(self):
        if self.load_thread is not None:
            return

        self.refresh_button.setEnabled(False)
        self._show_status("로봇 상태를 불러오는 중입니다.")
        self.load_thread, self.load_worker = start_worker_thread(
            self,
            worker=RobotStatusLoadWorker(selected_map_id=self.selected_map_id),
            finished_handler=self._handle_load_finished,
            clear_handler=self._clear_load_thread,
        )

    def _handle_load_finished(self, ok, payload):
        if not ok:
            self._show_status(f"로봇 상태를 불러오지 못했습니다. {payload}")
            return

        self.apply_robot_status_bundle(payload if isinstance(payload, dict) else {})
        self.status_label.setHidden(True)
        self.time_card.mark_updated()

    def _clear_load_thread(self):
        self.load_thread = None
        self.load_worker = None
        self.refresh_button.setEnabled(True)

    def apply_robot_status_bundle(self, bundle):
        bundle = bundle or {}
        summary = bundle.get("summary") or {}
        self.robots = [
            robot for robot in bundle.get("robots") or [] if isinstance(robot, dict)
        ]
        self.map_profiles = [
            profile
            for profile in bundle.get("map_profiles") or []
            if isinstance(profile, dict)
        ]
        self.selected_map_id = (
            str(bundle.get("selected_map_id") or "").strip()
            or self.selected_map_id
            or _selected_map_id(
                preferred_map_id=None,
                map_profiles=self.map_profiles,
                robots=self.robots,
            )
        )
        self.robots.sort(key=_robot_display_sort_key)

        self._apply_summary(summary)
        self._populate_map_selector()
        self._apply_robot_map(bundle)
        self._apply_robot_cards(self.robots)
        self._apply_robot_table(self.robots)
        self._apply_delivery_composition(bundle.get("delivery_composition") or [])

        if self.robots:
            self._render_detail(self.robots[0])
        else:
            self.detail_list.set_rows([], empty_text="표시할 로봇 상태가 없습니다.")

    def _apply_summary(self, summary):
        for key, _title in SUMMARY_ITEMS:
            value = int(summary.get(key) or 0)
            self.summary_cards[key].set_value(value, "대")

    def _apply_robot_cards(self, robots):
        self._clear_layout(self.card_grid)
        if not robots:
            empty = QLabel("표시할 로봇 상태가 없습니다.")
            empty.setObjectName("mutedText")
            self.card_grid.addWidget(empty, 0, 0)
            return

        for index, robot in enumerate(robots):
            self.card_grid.addWidget(RobotStatusCard(robot), index // 3, index % 3)

    def _populate_map_selector(self):
        self._syncing_map_selector = True
        try:
            self.map_selector.clear()
            for profile in self.map_profiles:
                map_id = str(profile.get("map_id") or "").strip()
                if not map_id:
                    continue
                map_name = str(profile.get("map_name") or "").strip()
                label = f"{map_name} ({map_id})" if map_name else map_id
                self.map_selector.addItem(label, map_id)
            index = self.map_selector.findData(self.selected_map_id)
            self.map_selector.setCurrentIndex(index if index >= 0 else 0)
            if self.map_selector.currentIndex() >= 0:
                self.selected_map_id = self.map_selector.currentData()
        finally:
            self._syncing_map_selector = False

    def _apply_robot_map(self, bundle):
        assets = bundle.get("map_assets") if isinstance(bundle, dict) else None
        assets = assets if isinstance(assets, dict) else {}
        asset_map_id = str(assets.get("map_id") or "").strip()
        if asset_map_id and asset_map_id == self.selected_map_id:
            self.robot_map_canvas.load_map_from_assets(
                yaml_text=str(assets.get("yaml_text") or ""),
                pgm_bytes=assets.get("pgm_bytes") or b"",
                cache_key=(
                    asset_map_id,
                    assets.get("yaml_sha256"),
                    assets.get("pgm_sha256"),
                ),
            )
        else:
            self.robot_map_canvas.clear_map("맵 asset 미수신")

        self.robot_map_canvas.show_robots(
            self.robots,
            selected_map_id=self.selected_map_id,
        )
        visible_count = len(self.robot_map_canvas.visible_robot_ids)
        total_count = len(self.robots)
        error = str(bundle.get("map_asset_error") or "").strip()
        if error:
            self.map_status_label.setText(error)
        elif self.selected_map_id:
            self.map_status_label.setText(
                f"선택 맵 {self.selected_map_id} · 표시 {visible_count}대 / "
                f"전체 {total_count}대"
            )
        else:
            self.map_status_label.setText("선택 가능한 맵이 없습니다.")

    def _handle_map_selection_changed(self, index):
        if self._syncing_map_selector:
            return
        selected_map_id = self.map_selector.itemData(index)
        selected_map_id = str(selected_map_id or "").strip() or None
        if not selected_map_id or selected_map_id == self.selected_map_id:
            return
        self.selected_map_id = selected_map_id
        self.refresh_data()

    def _apply_robot_table(self, robots):
        self.table.setRowCount(len(robots))
        for row_index, robot in enumerate(robots):
            values = [
                _display(robot.get("robot_id")),
                _display(robot.get("display_name")),
                _display(robot.get("robot_type")),
                _capabilities_text(robot.get("capabilities")),
                _display(robot.get("connection_status")),
                _display(robot.get("runtime_state")),
                _battery_text(robot.get("battery_percent")),
                _display(robot.get("current_task_id")),
                _datetime(robot.get("last_seen_at")),
            ]
            for column_index, value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(value))

    def _apply_delivery_composition(self, composition):
        for row in self.composition_rows:
            row.setParent(None)
            row.deleteLater()
        self.composition_rows = []

        for item in composition:
            if not isinstance(item, dict):
                continue
            row = KeyValueRow(_display(item.get("label")), _display(item.get("value")))
            self.composition_layout.addWidget(row)
            self.composition_rows.append(row)

    def _handle_table_selection(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if row < 0 or row >= len(self.robots):
            return
        self._render_detail(self.robots[row])

    def _render_detail(self, robot):
        detail_rows = [
            ("선택 로봇", _display(robot.get("robot_id"))),
            ("표시명", _display(robot.get("display_name"))),
            ("구분", _display(robot.get("robot_type"))),
            ("지원 기능", _capabilities_text(robot.get("capabilities"))),
            (
                "상태",
                f"{_display(robot.get('connection_status'))} / "
                f"{_display(robot.get('runtime_state'))}",
            ),
            ("현재 작업", _display(robot.get("current_task_id"))),
            ("현재 단계", _display(robot.get("current_phase"))),
            ("현재 위치", _display(robot.get("current_location"))),
            ("배터리", _battery_text(robot.get("battery_percent"))),
            ("마지막 수신", _datetime(robot.get("last_seen_at"))),
            ("Fault", _display(robot.get("fault_code"))),
        ]
        self.detail_list.set_rows(detail_rows)

    def _show_status(self, message: str):
        self.status_label.setText(message)
        self.status_label.setHidden(False)

    def reset_page(self):
        self.refresh_data()

    def shutdown(self):
        stop_worker_thread(
            self.load_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_load_thread,
        )

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                RobotStatusPage._clear_layout(child_layout)


__all__ = [
    "RobotStatusLoadWorker",
    "RobotStatusPage",
    "RobotStatusCard",
    "RobotLocationMapCanvas",
    "StatusChip",
    "SummaryCard",
]
