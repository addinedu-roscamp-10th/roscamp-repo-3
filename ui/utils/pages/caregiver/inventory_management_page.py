from __future__ import annotations

from PyQt6.QtCore import QObject, QDateTime, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.utils.core.worker_threads import start_worker_thread, stop_worker_thread
from ui.utils.network.service_clients import InventoryRemoteService
from ui.utils.widgets.admin_common import (
    SummaryCard,
    display_text as _display,
    int_value as _int_value,
)
from ui.utils.widgets.admin_shell import PageHeader


SUMMARY_ITEMS = (
    ("total_item_count", "전체 품목", "종"),
    ("total_quantity", "총 수량", "개"),
    ("low_stock_item_count", "부족 재고", "종"),
    ("empty_item_count", "품절", "종"),
)

TABLE_HEADERS = ["item_id", "item_type", "item_name", "quantity", "updated_at"]
SUCCESS_RESULT_CODES = {"OK", "UPDATED", "ACCEPTED"}


def _is_success_response(payload) -> bool:
    if isinstance(payload, dict):
        return str(payload.get("result_code") or "").upper() in SUCCESS_RESULT_CODES
    return False


class InventoryLoadWorker(QObject):
    finished = pyqtSignal(bool, object)

    def run(self):
        try:
            bundle = InventoryRemoteService().get_inventory_bundle() or {}
            self.finished.emit(True, bundle)
        except Exception as exc:
            self.finished.emit(False, str(exc))


class InventoryAdjustWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, payload):
        super().__init__()
        self.payload = payload if isinstance(payload, dict) else {}

    def run(self):
        try:
            service = InventoryRemoteService()
            mode = str(self.payload.get("mode") or "").upper()
            if mode == "SET":
                response = service.set_item_quantity(
                    item_id=self.payload.get("item_id"),
                    quantity=self.payload.get("quantity"),
                )
            else:
                response = service.add_item_quantity(
                    item_id=self.payload.get("item_id"),
                    quantity_delta=self.payload.get("quantity_delta"),
                )
            self.finished.emit(True, response or {})
        except Exception as exc:
            self.finished.emit(False, str(exc))


class InventoryManagementPage(QWidget):
    def __init__(self, *, autoload: bool = True):
        super().__init__()
        self._worker_stop_wait_ms = 1000
        self.load_thread = None
        self.load_worker = None
        self.adjust_thread = None
        self.adjust_worker = None
        self.items = []
        self.summary_cards = {}
        self.low_stock_labels = []

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
                "재고 관리",
                "운반 가능한 보급품 수량을 조회하고 item_id 기준으로 조정합니다.",
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
        self.refresh_button.setProperty("inventory_action", "refresh")
        self.refresh_button.clicked.connect(self.refresh_data)

        action_layout.addWidget(self.last_update_label)
        action_layout.addWidget(self.status_label)
        action_layout.addWidget(self.refresh_button)
        header_row.addWidget(action_card)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(16)
        for key, title, unit in SUMMARY_ITEMS:
            card = SummaryCard(title, initial_value=f"0{unit}")
            self.summary_cards[key] = card
            summary_row.addWidget(card)

        content_row = QHBoxLayout()
        content_row.setSpacing(18)

        table_card = QFrame()
        table_card.setObjectName("formCard")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(20, 20, 20, 20)
        table_layout.setSpacing(12)

        table_title = QLabel("보급품 현황")
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
        detail_title = QLabel("재고 상세")
        detail_title.setObjectName("sectionTitle")
        self.detail_label = QLabel("표에서 물품을 선택하세요.")
        self.detail_label.setObjectName("mutedText")
        self.detail_label.setWordWrap(True)
        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(self.detail_label)

        form_card = QFrame()
        form_card.setObjectName("formCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(10)
        form_title = QLabel("재고 추가 / 직접 수정")
        form_title.setObjectName("sectionTitle")

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("기존 수량에 추가", "ADD")
        self.mode_combo.addItem("현재 수량 직접 수정", "SET")
        self.mode_combo.currentIndexChanged.connect(self._sync_quantity_spin_for_mode)

        self.item_combo = QComboBox()
        self.item_combo.currentIndexChanged.connect(self._handle_combo_selection)

        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 999999)
        self.quantity_spin.setValue(1)

        self.apply_button = QPushButton("적용")
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.setProperty("inventory_action", "adjust")
        self.apply_button.clicked.connect(self.add_inventory)

        form_layout.addWidget(form_title)
        form_layout.addWidget(QLabel("조정 방식"))
        form_layout.addWidget(self.mode_combo)
        form_layout.addWidget(QLabel("물품"))
        form_layout.addWidget(self.item_combo)
        form_layout.addWidget(QLabel("수량"))
        form_layout.addWidget(self.quantity_spin)
        form_layout.addWidget(self.apply_button)

        warning_card = QFrame()
        warning_card.setObjectName("noticeCard")
        warning_layout = QVBoxLayout(warning_card)
        warning_layout.setContentsMargins(20, 20, 20, 20)
        warning_layout.setSpacing(10)
        warning_title = QLabel("부족 재고 경고")
        warning_title.setObjectName("sectionTitle")
        self.low_stock_layout = warning_layout
        warning_layout.addWidget(warning_title)

        side_column.addWidget(detail_card)
        side_column.addWidget(form_card)
        side_column.addWidget(warning_card)
        side_column.addStretch()

        content_row.addWidget(table_card, 2)
        content_row.addLayout(side_column, 1)

        root.addLayout(header_row)
        root.addLayout(summary_row)
        root.addLayout(content_row, 1)

    def refresh_data(self):
        if self.load_thread is not None:
            return

        self.refresh_button.setEnabled(False)
        self._show_status("재고 데이터를 불러오는 중입니다.")
        self.load_thread, self.load_worker = start_worker_thread(
            self,
            worker=InventoryLoadWorker(),
            finished_handler=self._handle_load_finished,
            clear_handler=self._clear_load_thread,
        )

    def _handle_load_finished(self, ok, payload):
        if not ok:
            self._show_status(f"재고 데이터를 불러오지 못했습니다. {payload}")
            return

        self.apply_inventory_bundle(payload if isinstance(payload, dict) else {})
        self.status_label.setHidden(True)
        now = QDateTime.currentDateTime().toString("HH:mm:ss")
        self.last_update_label.setText(f"마지막 업데이트: {now}")

    def _clear_load_thread(self):
        self.load_thread = None
        self.load_worker = None
        self.refresh_button.setEnabled(True)

    def apply_inventory_bundle(self, bundle):
        bundle = bundle or {}
        summary = bundle.get("summary") or {}
        self.items = [
            item for item in bundle.get("items") or [] if isinstance(item, dict)
        ]

        self._apply_summary(summary)
        self._apply_table(self.items)
        self._apply_item_combo(self.items)
        self._apply_low_stock_items(bundle.get("low_stock_items") or [])

        if self.items:
            self._render_detail(self.items[0])
        else:
            self.detail_label.setText("표시할 재고 데이터가 없습니다.")

    def _apply_summary(self, summary):
        for key, _title, unit in SUMMARY_ITEMS:
            value = _int_value(summary.get(key))
            self.summary_cards[key].set_value(value, unit)

    def _apply_table(self, items):
        self.table.setRowCount(len(items))
        for row_index, item in enumerate(items):
            values = [
                _display(item.get("item_id")),
                _display(item.get("item_type")),
                _display(item.get("item_name")),
                str(_int_value(item.get("quantity"))),
                _display(item.get("updated_at")),
            ]
            for column_index, value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(value))

    def _apply_item_combo(self, items):
        self.item_combo.blockSignals(True)
        self.item_combo.clear()
        for item in items:
            item_id = _display(item.get("item_id"), "")
            label = f"[{item_id}] {_display(item.get('item_name'))}"
            self.item_combo.addItem(label, item_id)
        self.item_combo.blockSignals(False)
        if self.item_combo.count():
            self.item_combo.setCurrentIndex(0)

    def _apply_low_stock_items(self, low_stock_items):
        for label in self.low_stock_labels:
            label.setParent(None)
            label.deleteLater()
        self.low_stock_labels = []

        rows = [row for row in low_stock_items if isinstance(row, dict)]
        if not rows:
            label = QLabel("부족 재고가 없습니다.")
            label.setObjectName("mutedText")
            self.low_stock_layout.addWidget(label)
            self.low_stock_labels.append(label)
            return

        for row in rows:
            quantity = row.get("quantity")
            label = QLabel(f"{_display(row.get('item_name'))}: {_int_value(quantity)}개")
            label.setObjectName("mutedText")
            self.low_stock_layout.addWidget(label)
            self.low_stock_labels.append(label)

    def _handle_table_selection(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if row < 0 or row >= len(self.items):
            return
        self._render_detail(self.items[row])
        self._select_combo_item(self.items[row].get("item_id"))

    def _handle_combo_selection(self):
        item_id = self.item_combo.currentData()
        item = self._find_item(item_id)
        if item is not None:
            self._render_detail(item)

    def _render_detail(self, item):
        detail_lines = [
            f"선택 물품: {_display(item.get('item_name'))}",
            f"item_id: {_display(item.get('item_id'))}",
            f"item_type: {_display(item.get('item_type'))}",
            f"현재 수량: {_int_value(item.get('quantity'))}개",
            f"updated_at: {_display(item.get('updated_at'))}",
        ]
        self.detail_label.setText("\n".join(detail_lines))

    def _collect_adjust_payload(self):
        item_id = self.item_combo.currentData()
        if not item_id:
            raise ValueError("물품을 선택하세요.")

        mode = str(self.mode_combo.currentData() or "ADD").upper()
        quantity = int(self.quantity_spin.value())
        if mode == "SET":
            return {
                "mode": "SET",
                "item_id": str(item_id),
                "quantity": quantity,
            }

        if quantity <= 0:
            raise ValueError("추가 수량은 1 이상이어야 합니다.")

        return {
            "mode": "ADD",
            "item_id": str(item_id),
            "quantity_delta": quantity,
        }

    def _sync_quantity_spin_for_mode(self):
        if str(self.mode_combo.currentData() or "").upper() == "SET":
            self.quantity_spin.setMinimum(0)
            return
        self.quantity_spin.setMinimum(1)

    def add_inventory(self):
        if self.adjust_thread is not None:
            return

        try:
            payload = self._collect_adjust_payload()
        except ValueError as exc:
            self._show_status(str(exc))
            return

        self.apply_button.setEnabled(False)
        self._show_status("재고 수량 변경을 요청하는 중입니다.")
        self.adjust_thread, self.adjust_worker = start_worker_thread(
            self,
            worker=InventoryAdjustWorker(payload),
            finished_handler=self._handle_adjust_finished,
            clear_handler=self._clear_adjust_thread,
        )

    def _handle_adjust_finished(self, ok, payload):
        if not ok:
            self._show_status(f"재고 수량을 변경하지 못했습니다. {payload}")
            return

        if not _is_success_response(payload):
            message = _display(
                payload.get("result_message") if isinstance(payload, dict) else payload
            )
            self._show_status(message)
            return

        message = payload.get("result_message") or "재고 수량을 변경했습니다."
        self.quantity_spin.setValue(1)
        self._show_status(message)
        self.refresh_data()

    def _clear_adjust_thread(self):
        self.adjust_thread = None
        self.adjust_worker = None
        self.apply_button.setEnabled(True)

    def _find_item(self, item_id):
        text = str(item_id or "")
        return next(
            (
                item
                for item in self.items
                if str(item.get("item_id") or "").strip() == text
            ),
            None,
        )

    def _select_combo_item(self, item_id):
        text = str(item_id or "")
        for index in range(self.item_combo.count()):
            if str(self.item_combo.itemData(index)) == text:
                self.item_combo.blockSignals(True)
                self.item_combo.setCurrentIndex(index)
                self.item_combo.blockSignals(False)
                break

    def _show_status(self, message: str):
        self.status_label.setText(message)
        self.status_label.setHidden(False)

    def load_inventory_data(self):
        self.refresh_data()

    def reset_page(self):
        self.quantity_spin.setValue(1)
        self.table.clearSelection()
        self.refresh_data()

    def shutdown(self):
        stop_worker_thread(
            self.load_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_load_thread,
        )
        stop_worker_thread(
            self.adjust_thread,
            wait_ms=self._worker_stop_wait_ms,
            clear_handler=self._clear_adjust_thread,
        )


__all__ = [
    "InventoryAdjustWorker",
    "InventoryLoadWorker",
    "InventoryManagementPage",
    "SummaryCard",
]
