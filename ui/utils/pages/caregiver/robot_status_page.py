from __future__ import annotations

from PyQt6.QtCore import QObject, QDateTime, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.utils.core.worker_threads import start_worker_thread, stop_worker_thread
from ui.utils.network.service_clients import CaregiverRemoteService
from ui.utils.widgets.admin_shell import PageHeader


SUMMARY_ITEMS = (
    ("total_robot_count", "전체 로봇"),
    ("online_robot_count", "온라인"),
    ("offline_robot_count", "오프라인"),
    ("caution_robot_count", "주의"),
)

TABLE_HEADERS = [
    "로봇 ID",
    "표시명",
    "역할",
    "연결",
    "상태",
    "배터리",
    "현재 작업",
    "마지막 수신",
]


def _display(value, default="-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _battery_text(value) -> str:
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return str(value)


def _chip_type(connection_status: str) -> str:
    normalized = str(connection_status or "").upper()
    if normalized == "ONLINE":
        return "green"
    if normalized == "DEGRADED":
        return "yellow"
    if normalized == "OFFLINE":
        return "red"
    return "blue"


class RobotStatusLoadWorker(QObject):
    finished = pyqtSignal(bool, object)

    def run(self):
        try:
            bundle = CaregiverRemoteService().get_robot_status_bundle() or {}
            self.finished.emit(True, bundle)
        except Exception as exc:
            self.finished.emit(False, str(exc))


class StatusChip(QLabel):
    def __init__(self, text: str, chip_type: str = "blue"):
        super().__init__(text)
        mapping = {
            "green": "chipGreen",
            "blue": "chipBlue",
            "red": "chipRed",
            "yellow": "chipYellow",
        }
        self.setObjectName(mapping.get(chip_type, "chipBlue"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class SummaryCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("mutedText")

        self.value_label = QLabel("0대")
        self.value_label.setObjectName("summaryValue")

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)


class RobotStatusCard(QFrame):
    def __init__(self, robot: dict):
        super().__init__()
        self.robot_id = robot.get("robot_id")
        self.setObjectName("card")

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

        display_name = QLabel(_display(robot.get("display_name")))
        display_name.setObjectName("mutedText")

        details = [
            f"유형/역할: {_display(robot.get('robot_type'))} / {_display(robot.get('scenario_role'))}",
            f"현재 작업: {_display(robot.get('current_task_id'))}",
            f"단계: {_display(robot.get('current_phase'))}",
            f"배터리: {_battery_text(robot.get('battery_percent'))}",
            f"마지막 수신: {_display(robot.get('last_seen_at'))}",
        ]

        layout.addLayout(title_row)
        layout.addWidget(display_name)
        for text in details:
            label = QLabel(text)
            label.setObjectName("mutedText")
            label.setWordWrap(True)
            layout.addWidget(label)


class RobotStatusPage(QWidget):
    def __init__(self, *, autoload: bool = True):
        super().__init__()
        self._worker_stop_wait_ms = 1000
        self.load_thread = None
        self.load_worker = None
        self.summary_cards = {}
        self.robots = []

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

        action_card = QFrame()
        action_card.setObjectName("card")
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(18, 16, 18, 16)
        action_layout.setSpacing(8)

        self.last_update_label = QLabel("마지막 업데이트: -")
        self.last_update_label.setObjectName("mutedText")
        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)
        self.status_label.setHidden(True)

        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.setObjectName("secondaryButton")
        self.refresh_button.setProperty("robot_status_action", "refresh")
        self.refresh_button.clicked.connect(self.refresh_data)

        action_layout.addWidget(self.last_update_label)
        action_layout.addWidget(self.status_label)
        action_layout.addWidget(self.refresh_button)
        header_row.addWidget(action_card)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(16)
        for key, title in SUMMARY_ITEMS:
            card = SummaryCard(title)
            self.summary_cards[key] = card
            summary_row.addWidget(card)

        self.card_grid = QGridLayout()
        self.card_grid.setHorizontalSpacing(16)
        self.card_grid.setVerticalSpacing(16)

        cards_wrap = QFrame()
        cards_wrap.setObjectName("card")
        cards_layout = QVBoxLayout(cards_wrap)
        cards_layout.setContentsMargins(20, 20, 20, 20)
        cards_layout.setSpacing(14)
        cards_title = QLabel("로봇 카드")
        cards_title.setObjectName("sectionTitle")
        cards_layout.addWidget(cards_title)
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
        self.detail_label = QLabel("테이블에서 로봇을 선택하세요.")
        self.detail_label.setObjectName("mutedText")
        self.detail_label.setWordWrap(True)
        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(self.detail_label)

        map_card = QFrame()
        map_card.setObjectName("noticeCard")
        map_layout = QVBoxLayout(map_card)
        map_layout.setContentsMargins(20, 20, 20, 20)
        map_layout.setSpacing(10)
        map_title = QLabel("맵/위치 시각화")
        map_title.setObjectName("sectionTitle")
        map_body = QLabel(
            "현재 phase 1에서는 좌표 텍스트를 표시합니다. 지도 기반 위치 시각화는 "
            "좌표/구역 설정의 맵 렌더링 컴포넌트를 재사용해 확장합니다."
        )
        map_body.setObjectName("mutedText")
        map_body.setWordWrap(True)
        map_layout.addWidget(map_title)
        map_layout.addWidget(map_body)

        composition_card = QFrame()
        composition_card.setObjectName("noticeCard")
        composition_layout = QVBoxLayout(composition_card)
        composition_layout.setContentsMargins(20, 20, 20, 20)
        composition_layout.setSpacing(8)
        composition_title = QLabel("운반 복합 로봇 구성")
        composition_title.setObjectName("sectionTitle")
        self.composition_labels = []
        composition_layout.addWidget(composition_title)

        side_column.addWidget(detail_card)
        side_column.addWidget(map_card)
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
            worker=RobotStatusLoadWorker(),
            finished_handler=self._handle_load_finished,
            clear_handler=self._clear_load_thread,
        )

    def _handle_load_finished(self, ok, payload):
        if not ok:
            self._show_status(f"로봇 상태를 불러오지 못했습니다. {payload}")
            return

        self.apply_robot_status_bundle(payload if isinstance(payload, dict) else {})
        self.status_label.setHidden(True)
        now = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.last_update_label.setText(f"마지막 업데이트: {now}")

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

        self._apply_summary(summary)
        self._apply_robot_cards(self.robots)
        self._apply_robot_table(self.robots)
        self._apply_delivery_composition(bundle.get("delivery_composition") or [])

        if self.robots:
            self._render_detail(self.robots[0])
        else:
            self.detail_label.setText("표시할 로봇 상태가 없습니다.")

    def _apply_summary(self, summary):
        for key, _title in SUMMARY_ITEMS:
            value = int(summary.get(key) or 0)
            self.summary_cards[key].value_label.setText(f"{value}대")

    def _apply_robot_cards(self, robots):
        self._clear_layout(self.card_grid)
        if not robots:
            empty = QLabel("표시할 로봇 상태가 없습니다.")
            empty.setObjectName("mutedText")
            self.card_grid.addWidget(empty, 0, 0)
            return

        for index, robot in enumerate(robots):
            self.card_grid.addWidget(RobotStatusCard(robot), index // 3, index % 3)

    def _apply_robot_table(self, robots):
        self.table.setRowCount(len(robots))
        for row_index, robot in enumerate(robots):
            values = [
                _display(robot.get("robot_id")),
                _display(robot.get("display_name")),
                _display(robot.get("scenario_role")),
                _display(robot.get("connection_status")),
                _display(robot.get("runtime_state")),
                _battery_text(robot.get("battery_percent")),
                _display(robot.get("current_task_id")),
                _display(robot.get("last_seen_at")),
            ]
            for column_index, value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(value))

    def _apply_delivery_composition(self, composition):
        for label in self.composition_labels:
            label.setParent(None)
            label.deleteLater()
        self.composition_labels = []

        for item in composition:
            if not isinstance(item, dict):
                continue
            label = QLabel(f"{_display(item.get('label'))}: {_display(item.get('value'))}")
            label.setObjectName("mutedText")
            self.composition_layout.addWidget(label)
            self.composition_labels.append(label)

    def _handle_table_selection(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if row < 0 or row >= len(self.robots):
            return
        self._render_detail(self.robots[row])

    def _render_detail(self, robot):
        detail_lines = [
            f"선택 로봇: {_display(robot.get('robot_id'))}",
            f"표시명: {_display(robot.get('display_name'))}",
            f"유형/역할: {_display(robot.get('robot_type'))} / {_display(robot.get('scenario_role'))}",
            f"상태: {_display(robot.get('connection_status'))} / {_display(robot.get('runtime_state'))}",
            f"현재 작업: {_display(robot.get('current_task_id'))}",
            f"현재 단계: {_display(robot.get('current_phase'))}",
            f"현재 위치: {_display(robot.get('current_location'))}",
            f"배터리: {_battery_text(robot.get('battery_percent'))}",
            f"마지막 수신: {_display(robot.get('last_seen_at'))}",
            f"Fault: {_display(robot.get('fault_code'))}",
        ]
        self.detail_label.setText("\n".join(detail_lines))

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
    "StatusChip",
    "SummaryCard",
]
