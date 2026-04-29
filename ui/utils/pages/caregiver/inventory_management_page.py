from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QComboBox
)
from ui.utils.network.service_clients import InventoryRemoteService
from ui.utils.widgets.admin_shell import PageHeader
from ui.utils.widgets.common import InlineStatusMixin


class InventoryManagementPage(QWidget, InlineStatusMixin):
    def __init__(self):
        super().__init__()
        self.inventory_service = InventoryRemoteService()
        self._build_ui()
        self.load_inventory_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        content_row = QHBoxLayout()
        content_row.setSpacing(18)

        table_card = QFrame()
        table_card.setObjectName("formCard")
        tc = QVBoxLayout(table_card)
        tc.setContentsMargins(20, 20, 20, 20)
        tc.setSpacing(12)

        table_title = QLabel("보급품 현황")
        table_title.setObjectName("sectionTitle")

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["물품 종류", "수량"])
        self.table.horizontalHeader().setStretchLastSection(True)

        tc.addWidget(table_title)
        tc.addWidget(self.table)

        form_card = QFrame()
        form_card.setObjectName("formCard")
        fc = QVBoxLayout(form_card)
        fc.setContentsMargins(20, 20, 20, 20)
        fc.setSpacing(12)

        form_title = QLabel("재고 추가 / 수정")
        form_title.setObjectName("sectionTitle")

        self.item_combo = QComboBox()
        self.item_combo.setMinimumHeight(44)

        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("수량 입력")
        self.init_inline_status()

        add_btn = QPushButton("재고 추가")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self.add_inventory)

        fc.addWidget(form_title)
        fc.addWidget(QLabel("물품 종류"))
        fc.addWidget(self.item_combo)
        fc.addWidget(QLabel("수량"))
        fc.addWidget(self.qty_input)
        fc.addWidget(self.status_label)
        fc.addWidget(add_btn)
        fc.addStretch()

        content_row.addWidget(table_card, 2)
        content_row.addWidget(form_card, 1)

        root.addWidget(
            PageHeader("재고 관리", "보급품 종류와 수량을 관리하고 표 형태로 확인합니다.")
        )
        root.addLayout(content_row, 1)

    def load_inventory_data(self):
        try:
            rows = self.inventory_service.get_inventory_rows()
            self.item_combo.clear()

            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                self.table.setItem(r, 0, QTableWidgetItem(str(row["item_name"])))
                self.table.setItem(r, 1, QTableWidgetItem(str(row["quantity"])))

            self.item_combo.addItems([str(row["item_name"]) for row in rows])
        except Exception as exc:
            self.show_inline_status(f"재고 데이터를 불러오지 못했습니다. {exc}", "error")

    def add_inventory(self):
        item_name = self.item_combo.currentText().strip()
        qty_text = self.qty_input.text().strip()

        if not item_name or not qty_text:
            self.show_inline_status("물품 종류와 수량을 입력하세요.", "warning")
            return

        try:
            quantity = int(qty_text)
        except ValueError:
            self.show_inline_status("수량은 숫자로 입력하세요.", "warning")
            return

        success, message = self.inventory_service.add_inventory(item_name, quantity)
        if not success:
            self.show_inline_status(message, "warning")
            return

        self.qty_input.clear()
        self.load_inventory_data()
        self.show_inline_status(message, "success")

    def reset_page(self):
        self.qty_input.clear()
        self.item_combo.setCurrentIndex(0 if self.item_combo.count() else -1)
        self.table.clearSelection()
        self.hide_inline_status()
        self.load_inventory_data()
