from __future__ import annotations

from PyQt6.QtCore import QObject, QDateTime, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.utils.core.worker_threads import start_worker_thread, stop_worker_thread
from ui.utils.network.service_clients import CaregiverRemoteService
from ui.utils.widgets.admin_common import SummaryCard, display_text as _display
from ui.utils.widgets.admin_shell import PageHeader


SUMMARY_ITEMS = (
    ("total_event_count", "전체 이벤트"),
    ("warning_count", "경고"),
    ("error_count", "오류"),
    ("critical_count", "긴급"),
)

TABLE_HEADERS = [
    "event_id",
    "occurred_at",
    "severity",
    "source_component",
    "task_id",
    "robot_id",
    "event_type",
    "message",
]


def _filter_text(widget: QLineEdit):
    text = widget.text().strip()
    return text or None


class AlertLogLoadWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, filters):
        super().__init__()
        self.filters = filters if isinstance(filters, dict) else {}

    def run(self):
        try:
            bundle = CaregiverRemoteService().get_alert_log_bundle(**self.filters) or {}
            self.finished.emit(True, bundle)
        except Exception as exc:
            self.finished.emit(False, str(exc))


class AlertLogPage(QWidget):
    related_task_requested = pyqtSignal(object)
    related_robot_requested = pyqtSignal(str)

    def __init__(self, *, autoload: bool = True):
        super().__init__()
        self._worker_stop_wait_ms = 1000
        self.load_thread = None
        self.load_worker = None
        self.events = []
        self.summary_cards = {}

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
                "알림/로그",
                "운영 이벤트, 오류, 작업 실패, 취소 실패, 통신 이슈를 확인합니다.",
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
        self.refresh_button.setProperty("alert_log_action", "refresh")
        self.refresh_button.clicked.connect(self.refresh_data)

        action_layout.addWidget(self.last_update_label)
        action_layout.addWidget(self.status_label)
        action_layout.addWidget(self.refresh_button)
        header_row.addWidget(action_card)

        filter_card = QFrame()
        filter_card.setObjectName("formCard")
        filter_layout = QGridLayout(filter_card)
        filter_layout.setContentsMargins(20, 20, 20, 20)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.setVerticalSpacing(10)

        self.period_combo = QComboBox()
        for label, value in (
            ("최근 24시간", "LAST_24_HOURS"),
            ("최근 1시간", "LAST_1_HOUR"),
            ("오늘", "TODAY"),
            ("전체", "ALL"),
        ):
            self.period_combo.addItem(label, value)

        self.severity_combo = QComboBox()
        for label, value in (
            ("전체", None),
            ("INFO", "INFO"),
            ("WARNING", "WARNING"),
            ("ERROR", "ERROR"),
            ("CRITICAL", "CRITICAL"),
        ):
            self.severity_combo.addItem(label, value)

        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("예: Control Service")
        self.task_id_input = QLineEdit()
        self.task_id_input.setPlaceholderText("예: 1001")
        self.robot_id_input = QLineEdit()
        self.robot_id_input.setPlaceholderText("예: pinky2")
        self.event_type_input = QLineEdit()
        self.event_type_input.setPlaceholderText("예: TASK_FAILED")

        filters = [
            ("기간", self.period_combo),
            ("심각도", self.severity_combo),
            ("source_component", self.source_input),
            ("task_id", self.task_id_input),
            ("robot_id", self.robot_id_input),
            ("event_type", self.event_type_input),
        ]

        for index, (label_text, widget) in enumerate(filters):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")
            filter_layout.addWidget(label, index // 3 * 2, index % 3)
            filter_layout.addWidget(widget, index // 3 * 2 + 1, index % 3)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(16)
        for key, title in SUMMARY_ITEMS:
            card = SummaryCard(title, initial_value="0건")
            self.summary_cards[key] = card
            summary_row.addWidget(card)

        content_row = QHBoxLayout()
        content_row.setSpacing(18)

        table_card = QFrame()
        table_card.setObjectName("formCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(20, 20, 20, 20)
        table_layout.setSpacing(12)
        table_title = QLabel("운영 이벤트 목록")
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
        detail_title = QLabel("이벤트 상세")
        detail_title.setObjectName("sectionTitle")
        self.detail_label = QLabel("이벤트를 선택하세요.")
        self.detail_label.setObjectName("mutedText")
        self.detail_label.setWordWrap(True)
        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(self.detail_label)

        related_card = QFrame()
        related_card.setObjectName("noticeCard")
        related_layout = QVBoxLayout(related_card)
        related_layout.setContentsMargins(20, 20, 20, 20)
        related_layout.setSpacing(10)
        related_title = QLabel("관련 작업/로봇")
        related_title.setObjectName("sectionTitle")
        self.related_label = QLabel("선택된 이벤트의 task_id와 robot_id를 표시합니다.")
        self.related_label.setObjectName("mutedText")
        self.related_label.setWordWrap(True)
        self.related_task_button = QPushButton("작업 모니터에서 보기")
        self.related_task_button.setObjectName("secondaryButton")
        self.related_task_button.setEnabled(False)
        self.related_task_button.clicked.connect(self._emit_related_task)
        self.related_robot_button = QPushButton("로봇 상태에서 보기")
        self.related_robot_button.setObjectName("secondaryButton")
        self.related_robot_button.setEnabled(False)
        self.related_robot_button.clicked.connect(self._emit_related_robot)
        related_layout.addWidget(related_title)
        related_layout.addWidget(self.related_label)
        related_layout.addWidget(self.related_task_button)
        related_layout.addWidget(self.related_robot_button)

        side_column.addWidget(detail_card)
        side_column.addWidget(related_card)
        side_column.addStretch()

        content_row.addWidget(table_card, 2)
        content_row.addLayout(side_column, 1)

        root.addLayout(header_row)
        root.addWidget(filter_card)
        root.addLayout(summary_row)
        root.addLayout(content_row, 1)

    def refresh_data(self):
        if self.load_thread is not None:
            return

        self.refresh_button.setEnabled(False)
        self._show_status("알림/로그를 불러오는 중입니다.")
        self.load_thread, self.load_worker = start_worker_thread(
            self,
            worker=AlertLogLoadWorker(self._collect_filters()),
            finished_handler=self._handle_load_finished,
            clear_handler=self._clear_load_thread,
        )

    def _collect_filters(self):
        return {
            "period": self.period_combo.currentData(),
            "severity": self.severity_combo.currentData(),
            "source_component": _filter_text(self.source_input),
            "task_id": _filter_text(self.task_id_input),
            "robot_id": _filter_text(self.robot_id_input),
            "event_type": _filter_text(self.event_type_input),
            "limit": 100,
        }

    def _handle_load_finished(self, ok, payload):
        if not ok:
            self._show_status(f"알림/로그를 불러오지 못했습니다. {payload}")
            return

        self.apply_alert_log_bundle(payload if isinstance(payload, dict) else {})
        self.status_label.setHidden(True)
        now = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.last_update_label.setText(f"마지막 업데이트: {now}")

    def _clear_load_thread(self):
        self.load_thread = None
        self.load_worker = None
        self.refresh_button.setEnabled(True)

    def apply_alert_log_bundle(self, bundle):
        bundle = bundle or {}
        summary = bundle.get("summary") or {}
        self.events = [
            event for event in bundle.get("events") or [] if isinstance(event, dict)
        ]

        self._apply_summary(summary)
        self._apply_event_table(self.events)
        if self.events:
            self._render_detail(self.events[0])
        else:
            self.detail_label.setText("표시할 운영 이벤트가 없습니다.")
            self.related_label.setText("선택된 이벤트가 없습니다.")
            self._sync_related_actions({})

    def _apply_summary(self, summary):
        for key, _title in SUMMARY_ITEMS:
            value = int(summary.get(key) or 0)
            self.summary_cards[key].set_value(value, "건")

    def _apply_event_table(self, events):
        self.table.setRowCount(len(events))
        for row_index, event in enumerate(events):
            values = [
                _display(event.get("event_id")),
                _display(event.get("occurred_at")),
                _display(event.get("severity")),
                _display(event.get("source_component")),
                _display(event.get("task_id")),
                _display(event.get("robot_id")),
                _display(event.get("event_type")),
                _display(event.get("message"), ""),
            ]
            for column_index, value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(value))

    def _handle_table_selection(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if row < 0 or row >= len(self.events):
            return
        self._render_detail(self.events[row])

    def _render_detail(self, event):
        detail_lines = [
            f"event_id: {_display(event.get('event_id'))}",
            f"occurred_at: {_display(event.get('occurred_at'))}",
            f"severity: {_display(event.get('severity'))}",
            f"source_component: {_display(event.get('source_component'))}",
            f"event_type: {_display(event.get('event_type'))}",
            f"result_code: {_display(event.get('result_code'))}",
            f"reason_code: {_display(event.get('reason_code'))}",
            f"message: {_display(event.get('message'), '')}",
            f"payload: {_display(event.get('payload'))}",
        ]
        self.detail_label.setText("\n".join(detail_lines))
        self.related_label.setText(
            f"task_id={_display(event.get('task_id'))}\n"
            f"robot_id={_display(event.get('robot_id'))}"
        )
        self._sync_related_actions(event)

    def _sync_related_actions(self, event):
        task_id = event.get("task_id")
        robot_id = event.get("robot_id")
        self.related_task_button.setProperty("task_id", task_id)
        self.related_task_button.setEnabled(task_id is not None)
        self.related_robot_button.setProperty("robot_id", robot_id)
        self.related_robot_button.setEnabled(bool(robot_id))

    def _emit_related_task(self):
        task_id = self.related_task_button.property("task_id")
        if task_id is not None:
            self.related_task_requested.emit(task_id)

    def _emit_related_robot(self):
        robot_id = self.related_robot_button.property("robot_id")
        if robot_id:
            self.related_robot_requested.emit(str(robot_id))

    def _show_status(self, message: str):
        self.status_label.setText(message)
        self.status_label.setHidden(False)

    def reset_page(self):
        self.table.clearSelection()
        self.refresh_data()

    def shutdown(self):
        stop_worker_thread(
            self.load_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_load_thread,
        )


__all__ = [
    "AlertLogLoadWorker",
    "AlertLogPage",
    "SummaryCard",
]
