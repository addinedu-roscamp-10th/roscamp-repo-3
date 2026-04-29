import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, QDateTime, pyqtSignal

from ui.utils.core.styles import load_stylesheet
from ui.utils.pages.visitor.staff_call_page import StaffCallPage
from ui.utils.pages.visitor.visit_guide_page import VisitGuidePage
from ui.utils.session.session_manager import SessionManager


class ActionCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, icon_text, title_text, desc_text):
        super().__init__()
        self.setObjectName("actionCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)

        self.icon = QLabel(icon_text)
        self.icon.setObjectName("cardIcon")

        self.title = QLabel(title_text)
        self.title.setObjectName("cardTitle")

        self.desc = QLabel(desc_text)
        self.desc.setObjectName("cardDesc")
        self.desc.setWordWrap(True)

        self.action_btn = QPushButton("바로가기")
        self.action_btn.setObjectName("cardButton")

        layout.addWidget(self.icon)
        layout.addWidget(self.title)
        layout.addWidget(self.desc)
        layout.addStretch()
        layout.addWidget(self.action_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self.action_btn.clicked.connect(self.clicked.emit)

        for widget in [self.icon, self.title, self.desc]:
            widget.mousePressEvent = self._child_click

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _child_click(self, event):
        self.clicked.emit()


class InfoCard(QFrame):
    def __init__(self, label_text, value_text):
        super().__init__()
        self.setObjectName("infoCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("infoLabel")

        value = QLabel(value_text)
        value.setObjectName("infoValue")
        value.setWordWrap(True)

        layout.addWidget(label)
        layout.addWidget(value)


class VisitorHomePage(QWidget):
    def __init__(self, go_guide_page=None, go_call_page=None):
        super().__init__()

        self.go_guide_page = go_guide_page
        self.go_call_page = go_call_page

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(18)

        title = QLabel("방문객 안내 화면")
        title.setObjectName("pageTitle")

        subtitle = QLabel("원하시는 서비스를 선택해주세요")
        subtitle.setObjectName("pageSubtitle")

        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(16)
        info_grid.setVerticalSpacing(16)

        self.location_card = InfoCard("현재 위치", "1층 로비")
        self.visit_time_card = InfoCard("방문 가능 시간", "09:00 ~ 18:00")
        self.robot_state_card = InfoCard("안내 로봇 상태", "이용 가능")

        info_grid.addWidget(self.location_card, 0, 0)
        info_grid.addWidget(self.visit_time_card, 0, 1)
        info_grid.addWidget(self.robot_state_card, 0, 2)

        action_title = QLabel("무엇을 도와드릴까요?")
        action_title.setObjectName("sectionTitle")

        action_grid = QGridLayout()
        action_grid.setHorizontalSpacing(18)
        action_grid.setVerticalSpacing(18)

        self.patient_card = ActionCard(
            "🧑‍⚕️",
            "어르신 찾기",
            "어르신 이름으로 위치와 병실 정보를 확인합니다."
        )

        self.call_card = ActionCard(
            "📞",
            "직원 호출",
            "도움이 필요할 때 직원에게 요청을 보냅니다."
        )

        action_grid.addWidget(self.patient_card, 0, 0)
        action_grid.addWidget(self.call_card, 0, 1)

        notice = QFrame()
        notice.setObjectName("noticeCard")
        notice_layout = QVBoxLayout(notice)
        notice_layout.setContentsMargins(18, 16, 18, 16)
        notice_layout.setSpacing(6)

        notice_title = QLabel("안내")
        notice_title.setObjectName("noticeTitle")

        notice_text = QLabel(
            "어르신 정보는 개인정보 보호를 위해 일부만 표시될 수 있습니다. "
            "직접 도움이 필요하시면 직원 호출을 이용해주세요."
        )
        notice_text.setObjectName("noticeText")
        notice_text.setWordWrap(True)

        notice_layout.addWidget(notice_title)
        notice_layout.addWidget(notice_text)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addLayout(info_grid)
        root.addSpacing(6)
        root.addWidget(action_title)
        root.addLayout(action_grid)
        root.addWidget(notice)
        root.addStretch()

        self.patient_card.clicked.connect(self._go_guide)
        self.call_card.clicked.connect(self._go_call)

    def _go_guide(self):
        if self.go_guide_page:
            self.go_guide_page()

    def _go_call(self):
        if self.go_call_page:
            self.go_call_page()


class VisitorMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("방문객 메인")
        self.resize(1200, 760)
        self.login_window = None
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        top = QHBoxLayout()

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(4)

        title = QLabel("방문객 안내 시스템")
        title.setObjectName("pageTitle")

        desc = QLabel("필요한 메뉴를 선택해 주세요")
        desc.setObjectName("topDescription")

        title_wrap.addWidget(title)
        title_wrap.addWidget(desc)

        top.addLayout(title_wrap)
        top.addStretch()

        self.time_box = QFrame()
        self.time_box.setObjectName("timeCard")
        time_layout = QVBoxLayout(self.time_box)
        time_layout.setContentsMargins(18, 12, 18, 12)
        time_layout.setSpacing(2)

        self.time_label = QLabel()
        self.time_label.setObjectName("timeLabel")

        self.date_label = QLabel()
        self.date_label.setObjectName("dateLabel")

        time_layout.addWidget(self.time_label, alignment=Qt.AlignmentFlag.AlignRight)
        time_layout.addWidget(self.date_label, alignment=Qt.AlignmentFlag.AlignRight)

        logout_btn = QPushButton("로그아웃")
        logout_btn.setObjectName("dangerButton")
        logout_btn.clicked.connect(self.logout)

        top.addWidget(self.time_box)
        top.addWidget(logout_btn)

        self.stack = QStackedWidget()

        self.call_page = StaffCallPage(
            go_home_page=lambda: self.stack.setCurrentWidget(self.home_page)
        )

        self.home_page = VisitorHomePage()

        self.guide_page = VisitGuidePage(
            go_home_page=lambda: self.stack.setCurrentWidget(self.home_page)
        )

        self.home_page.go_guide_page = lambda: self.stack.setCurrentWidget(self.guide_page)
        self.home_page.go_call_page = lambda: self.stack.setCurrentWidget(self.call_page)

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.guide_page)
        self.stack.addWidget(self.call_page)

        root.addLayout(top)
        root.addWidget(self.stack, 1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_datetime)
        self.timer.start(1000)
        self.update_datetime()

    def update_datetime(self):
        now = QDateTime.currentDateTime()
        self.time_label.setText(now.toString("HH:mm"))
        self.date_label.setText(now.toString("yyyy.MM.dd"))

    def logout(self):
        SessionManager.logout()
        self.login_window = None
        self.stack.setCurrentWidget(self.home_page)


__all__ = ["VisitorMainWindow", "load_stylesheet"]


def main():
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())

    window = VisitorMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
