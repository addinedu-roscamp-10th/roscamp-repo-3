from uuid import uuid4

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QComboBox, QTextEdit, QPushButton
)

from ui.utils.network.service_clients import StaffCallRemoteService

try:
    from ui.utils.session.session_manager import SessionManager
except Exception:  # pragma: no cover
    SessionManager = None


class StaffCallPage(QWidget):
    def __init__(self, go_home_page=None):
        super().__init__()
        self.go_home_page = go_home_page
        self.service = StaffCallRemoteService()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("직원 호출")
        title.setObjectName("pageTitle")
        subtitle = QLabel("방문객이 도움이 필요할 때 호출 내용을 등록합니다.")
        subtitle.setObjectName("pageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        chip = QLabel("Call")
        chip.setObjectName("chipRed")

        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(chip)

        form = QFrame()
        form.setObjectName("formCard")
        f = QVBoxLayout(form)
        f.setContentsMargins(24, 24, 24, 24)
        f.setSpacing(12)

        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "면회 위치 안내",
            "방문 등록 도움",
            "어르신 안내 요청",
            "긴급 호출",
            "기타 문의",
        ])

        self.detail_input = QTextEdit()
        self.detail_input.setPlaceholderText("요청 내용을 입력하세요.")

        self.status_label = QLabel("대기 중")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)

        f.addWidget(QLabel("요청 유형"))
        f.addWidget(self.type_combo)
        f.addWidget(QLabel("요청 상세"))
        f.addWidget(self.detail_input)
        f.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.back_btn = QPushButton("뒤로가기")
        self.back_btn.setObjectName("secondaryButton")
        self.back_btn.clicked.connect(self.go_back)

        self.submit_btn = QPushButton("직원 호출")
        self.submit_btn.setObjectName("dangerButton")
        self.submit_btn.clicked.connect(self.submit)

        btn_row.addWidget(self.back_btn)
        btn_row.addWidget(self.submit_btn)
        f.addLayout(btn_row)

        root.addLayout(header)
        root.addWidget(form)
        root.addStretch()

    def _current_visitor_id(self):
        if SessionManager is None:
            return None
        try:
            current_user = SessionManager.current_user()
            if current_user is None or getattr(current_user, "role", None) != "VISITOR":
                return None
            return getattr(current_user, "user_id", None)
        except Exception:
            return None

    def submit(self):
        result = self.service.submit_staff_call(
            call_type=self.type_combo.currentText(),
            description=self.detail_input.toPlainText(),
            idempotency_key=f"visitor_staff_call_{uuid4().hex}",
            visitor_id=self._current_visitor_id(),
        )
        success = result.get("result_code") == "ACCEPTED"
        message = result.get("result_message") or "직원 호출 처리 결과를 확인할 수 없습니다."

        self.status_label.setText(message)
        self.status_label.setObjectName("chipGreen" if success else "chipRed")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        if success:
            self.detail_input.clear()

    def go_back(self):
        if self.go_home_page:
            self.go_home_page()
