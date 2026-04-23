from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit
)

from ui.utils.network.service_clients import VisitGuideRemoteService

try:
    from ui.utils.session.session_manager import SessionManager
except Exception:  # pragma: no cover
    SessionManager = None


class VisitGuidePage(QWidget):
    def __init__(self, go_home_page=None):
        super().__init__()
        self.go_home_page = go_home_page
        self.service = VisitGuideRemoteService()
        self.selected_patient = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(18)

        title = QLabel("어르신 찾기")
        title.setObjectName("pageTitle")

        subtitle = QLabel("어르신 이름이나 병실로 검색한 뒤, 위치 확인 또는 로봇 안내를 시작할 수 있습니다.")
        subtitle.setObjectName("pageSubtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        search_card = QFrame()
        search_card.setObjectName("card")
        search_layout = QVBoxLayout(search_card)
        search_layout.setContentsMargins(22, 22, 22, 22)
        search_layout.setSpacing(14)

        search_title = QLabel("어르신 검색")
        search_title.setObjectName("sectionTitle")

        search_row = QHBoxLayout()
        search_row.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("어르신 이름 또는 병실을 입력하세요")
        self.search_input.returnPressed.connect(self.search_patient)

        self.search_btn = QPushButton("검색")
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.clicked.connect(self.search_patient)

        search_row.addWidget(self.search_input, 1)
        search_row.addWidget(self.search_btn)

        search_layout.addWidget(search_title)
        search_layout.addLayout(search_row)
        root.addWidget(search_card)

        content_row = QHBoxLayout()
        content_row.setSpacing(18)

        detail_card = QFrame()
        detail_card.setObjectName("card")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(22, 22, 22, 22)
        detail_layout.setSpacing(12)

        detail_title = QLabel("어르신 정보")
        detail_title.setObjectName("sectionTitle")

        self.name_label = QLabel("어르신명: 선택 전")
        self.room_label = QLabel("병실: -")
        self.location_label = QLabel("위치: -")
        self.visit_label = QLabel("면회 상태: -")

        self.status_label = QLabel("상태: 어르신 이름을 검색하면 정보가 표시됩니다.")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)

        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        self.robot_btn = QPushButton("로봇 안내 시작")
        self.robot_btn.setObjectName("primaryButton")
        self.robot_btn.clicked.connect(self.start_robot_guide)

        self.reset_btn = QPushButton("다시 검색")
        self.reset_btn.setObjectName("secondaryButton")
        self.reset_btn.clicked.connect(self.reset_search)

        self.back_btn = QPushButton("뒤로가기")
        self.back_btn.setObjectName("secondaryButton")
        self.back_btn.clicked.connect(self.go_back)

        action_row.addWidget(self.robot_btn, 2)
        action_row.addWidget(self.reset_btn, 1)
        action_row.addWidget(self.back_btn, 1)

        for btn in [self.robot_btn, self.reset_btn, self.back_btn]:
            btn.setMinimumHeight(48)

        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(self.name_label)
        detail_layout.addWidget(self.room_label)
        detail_layout.addWidget(self.location_label)
        detail_layout.addWidget(self.visit_label)
        detail_layout.addWidget(self.status_label)
        detail_layout.addStretch()
        detail_layout.addLayout(action_row)

        content_row.addWidget(detail_card, 1)
        root.addLayout(content_row)
        root.addStretch()

    def _current_member_id(self):
        if SessionManager is None:
            return None
        try:
            current_user = SessionManager.current_user()
            return None if current_user is None else getattr(current_user, "user_id", None)
        except Exception:
            return None

    def search_patient(self):
        ok, message, patient = self.service.search_patient(self.search_input.text())
        self.selected_patient = patient if ok else None

        if not ok:
            self.name_label.setText("어르신명: 선택 전")
            self.room_label.setText("병실: -")
            self.location_label.setText("위치: -")
            self.visit_label.setText("면회 상태: -")
            self.status_label.setText(f"상태: {message}")
            return

        self.name_label.setText(f"어르신명: {patient['name']}")
        self.room_label.setText(f"병실: {patient['room']}")
        self.location_label.setText(f"위치: {patient['location']}")
        self.visit_label.setText(f"면회 상태: {patient['status']}")
        self.status_label.setText("상태: 검색 결과를 확인했습니다.")

    def start_robot_guide(self):
        success, message = self.service.start_robot_guide(
            self.selected_patient,
            member_id=self._current_member_id(),
        )
        if success and self.selected_patient:
            self.status_label.setText(
                f"상태: {self.selected_patient['name']} 님의 {self.selected_patient['room']} 방향으로 로봇 안내를 시작합니다."
            )
        else:
            self.status_label.setText(f"상태: {message}")

    def reset_search(self):
        self.search_input.clear()
        self.selected_patient = None
        self.name_label.setText("어르신명: 선택 전")
        self.room_label.setText("병실: -")
        self.location_label.setText("위치: -")
        self.visit_label.setText("면회 상태: -")
        self.status_label.setText("상태: 어르신 이름을 검색하면 정보가 표시됩니다.")

    def go_back(self):
        if self.go_home_page:
            self.go_home_page()
