from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem
)


class RobotStatusPage(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._setup_timer()
        self.refresh_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("로봇 상태 조회")
        title.setObjectName("pageTitle")
        subtitle = QLabel("운영 중인 로봇의 위치, 배터리, 작업 상태를 확인합니다.")
        subtitle.setObjectName("pageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        chip = QLabel("실시간 연결")
        chip.setObjectName("chipGreen")

        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(chip)

        status_row = QHBoxLayout()
        status_row.setSpacing(16)

        for name, value, chip_name in [
            ("메인 서버", "정상", "chipGreen"),
            ("ROS2 통신", "연결됨", "chipBlue"),
            ("맵 서버", "준비", "chipYellow"),
        ]:
            box = QFrame()
            box.setObjectName("infoBox")
            b = QVBoxLayout(box)
            b.setContentsMargins(18, 16, 18, 16)

            lbl1 = QLabel(name)
            lbl1.setObjectName("mutedText")
            lbl2 = QLabel(value)
            lbl2.setObjectName("bigValue")
            lbl3 = QLabel("status")
            lbl3.setObjectName(chip_name)

            b.addWidget(lbl1)
            b.addWidget(lbl2)
            b.addWidget(lbl3)
            status_row.addWidget(box)

        table_card = QFrame()
        table_card.setObjectName("formCard")
        tc = QVBoxLayout(table_card)
        tc.setContentsMargins(20, 20, 20, 20)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["로봇", "위치", "배터리", "상태"])
        self.table.horizontalHeader().setStretchLastSection(True)

        tc.addWidget(self.table)

        root.addLayout(header)
        root.addLayout(status_row)
        root.addWidget(table_card, 1)

    def _setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(3000)

    def refresh_data(self):
        rows = [
            ["Pinky-01", "305호 이동 중", "82%", "경로 정상"],
            ["Pinky-02", "간호 스테이션", "64%", "대기"],
            ["Pinky-03", "3층 복도", "37%", "충전 필요"],
        ]
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem(value))