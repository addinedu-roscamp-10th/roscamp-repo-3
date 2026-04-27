from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QComboBox, QTextEdit, QPushButton, QLabel
from ui.utils.widgets.common import InlineStatusMixin, page_title

class RobotCallPage(QWidget, InlineStatusMixin):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.addWidget(page_title("로봇 호출", "호출 위치와 요청 대상을 선택하세요."))

        form = QFormLayout()
        self.location_combo = QComboBox()
        self.location_combo.addItems(["간호 스테이션", "3층 복도", "305호 앞", "면회실 앞"])
        self.robot_combo = QComboBox()
        self.robot_combo.addItems(["자동 선택", "Pinky-01", "Pinky-02", "Pinky-03"])
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["일반", "긴급"])
        self.purpose_combo = QComboBox()
        self.purpose_combo.addItems(["어르신 안내", "물품 수령", "보호사 보조", "기타"])
        self.memo_input = QTextEdit()
        self.init_inline_status()

        form.addRow("호출 위치", self.location_combo)
        form.addRow("배정 로봇", self.robot_combo)
        form.addRow("요청 우선순위", self.priority_combo)
        form.addRow("호출 목적", self.purpose_combo)
        form.addRow("요청 메모", self.memo_input)
        root.addLayout(form)

        root.addWidget(QLabel("예상 도착 시간: 약 1분 30초"))
        root.addWidget(QLabel("가용 로봇 수: 2대"))
        root.addWidget(QLabel("통신 상태: 정상"))
        root.addWidget(QLabel("호출 상태: 입력 대기"))
        root.addWidget(self.status_label)

        submit_btn = QPushButton("로봇 호출")
        submit_btn.setObjectName("primaryButton")
        submit_btn.clicked.connect(self.submit)
        root.addWidget(submit_btn)

    def submit(self):
        self.show_inline_status("로봇 호출 요청이 전송되었습니다.", "success")
