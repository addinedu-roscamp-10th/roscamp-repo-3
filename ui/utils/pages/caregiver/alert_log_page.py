from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem
from ui.utils.widgets.common import page_title
from ui.utils.mock_data import ALERTS

class AlertLogPage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.addWidget(page_title("date / 알림 / 오류 확인", "최근 경고와 오류 로그를 확인합니다."))

        self.list_widget = QListWidget()
        for date, level, message in ALERTS:
            item = QListWidgetItem(f"[{date}] [{level}] {message}")
            self.list_widget.addItem(item)
        root.addWidget(self.list_widget)

    def reset_page(self):
        self.list_widget.clearSelection()
        self.list_widget.setCurrentItem(None)
        self.list_widget.scrollToTop()
