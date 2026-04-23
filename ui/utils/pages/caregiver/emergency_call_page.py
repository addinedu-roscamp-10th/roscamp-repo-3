from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QComboBox, QTextEdit, QPushButton
from ui.utils.widgets.common import InlineStatusMixin, page_title

class EmergencyCallPage(QWidget, InlineStatusMixin):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.addWidget(page_title("긴급 호출", "우선순위가 높은 긴급 요청을 등록합니다."))

        form = QFormLayout()
        self.location_combo = QComboBox()
        self.location_combo.addItems(["302호", "305호", "복도", "면회실"])
        self.type_combo = QComboBox()
        self.type_combo.addItems(["어르신 이상 징후", "낙상 의심", "즉시 지원 요청", "기타 긴급 상황"])
        self.detail_input = QTextEdit()
        self.init_inline_status()

        form.addRow("위치", self.location_combo)
        form.addRow("긴급 유형", self.type_combo)
        form.addRow("상세 내용", self.detail_input)
        root.addLayout(form)
        root.addWidget(self.status_label)

        submit_btn = QPushButton("긴급 호출 접수")
        submit_btn.setObjectName("dangerButton")
        submit_btn.clicked.connect(self.submit)
        root.addWidget(submit_btn)

    def submit(self):
        self.show_inline_status("긴급 호출이 접수되었습니다.", "success")
