from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QHBoxLayout
from ui.utils.widgets.common import make_card, make_stat_box, page_title
from ui.utils.mock_data import INVENTORY, TODAY_STATS, ROBOTS, SCHEDULE

class CaregiverHomePage(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.addWidget(page_title("보호사 메인 화면", "요양원 보조 로봇 시스템의 주요 기능과 상태를 확인하세요."))

        grid = QGridLayout()
        grid.setSpacing(16)

        card1, body1 = make_card("생필품 재고", "Inventory")
        for name, desc, state, count in INVENTORY:
            row = QHBoxLayout()
            left = QVBoxLayout()
            left.addWidget(QLabel(f"<b>{name}</b>"))
            sub = QLabel(desc)
            sub.setObjectName("muted")
            left.addWidget(sub)
            right = QVBoxLayout()
            right.addWidget(QLabel(state))
            right.addWidget(QLabel(f"<b>{count}</b>"))
            row.addLayout(left)
            row.addStretch()
            row.addLayout(right)
            body1.addLayout(row)
        grid.addWidget(card1, 0, 0)

        card2, body2 = make_card("오늘 업무 현황", "실시간")
        stat_grid = QGridLayout()
        for i, (label, value) in enumerate(TODAY_STATS):
            stat_grid.addWidget(make_stat_box(label, value), i // 2, i % 2)
        body2.addLayout(stat_grid)
        grid.addWidget(card2, 0, 1)

        card3, body3 = make_card("로봇 상태", "정상 운영")
        for name, desc, battery in ROBOTS:
            row = QHBoxLayout()
            left = QVBoxLayout()
            left.addWidget(QLabel(f"<b>{name}</b>"))
            sub = QLabel(desc)
            sub.setObjectName("muted")
            left.addWidget(sub)
            row.addLayout(left)
            row.addStretch()
            row.addWidget(QLabel(f"<b>{battery}</b>"))
            body3.addLayout(row)
        grid.addWidget(card3, 1, 0)

        card4, body4 = make_card("오늘 일정")
        for time, title, desc in SCHEDULE:
            body4.addWidget(QLabel(f"<b>{time}</b>  {title}"))
            sub = QLabel(desc)
            sub.setObjectName("muted")
            body4.addWidget(sub)
        grid.addWidget(card4, 1, 1)

        root.addLayout(grid)
