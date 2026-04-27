from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QPushButton
)

from ui.utils.network.service_clients import VisitorRegisterRemoteService

try:
    from ui.utils.session.session_manager import SessionManager
except Exception:  # pragma: no cover
    SessionManager = None


class VisitorRegisterPage(QWidget):
    def __init__(self):
        super().__init__()
        self.service = VisitorRegisterRemoteService()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("방문 등록")
        title.setObjectName("pageTitle")
        subtitle = QLabel("방문객 정보를 입력하고 방문 등록을 진행하세요.")
        subtitle.setObjectName("pageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        chip = QLabel("Visitor")
        chip.setObjectName("chipBlue")

        header.addLayout(title_box)
        header.addStretch()
        header.addWidget(chip)

        form = QFrame()
        form.setObjectName("formCard")
        f = QVBoxLayout(form)
        f.setContentsMargins(24, 24, 24, 24)
        f.setSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("이름 입력")

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("010-0000-0000")

        self.patient_input = QLineEdit()
        self.patient_input.setPlaceholderText("어르신 이름 입력")

        self.relation_input = QLineEdit()
        self.relation_input.setPlaceholderText("관계 입력")

        self.purpose_input = QLineEdit()
        self.purpose_input.setPlaceholderText("방문 목적 입력")

        self.status_label = QLabel("등록 대기 중")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)

        f.addWidget(QLabel("방문객 이름"))
        f.addWidget(self.name_input)
        f.addWidget(QLabel("연락처"))
        f.addWidget(self.phone_input)
        f.addWidget(QLabel("어르신 이름"))
        f.addWidget(self.patient_input)
        f.addWidget(QLabel("관계"))
        f.addWidget(self.relation_input)
        f.addWidget(QLabel("방문 목적"))
        f.addWidget(self.purpose_input)
        f.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.submit_btn = QPushButton("방문 등록")
        self.submit_btn.setObjectName("primaryButton")
        self.submit_btn.clicked.connect(self.submit)

        btn_row.addWidget(self.submit_btn)
        f.addLayout(btn_row)

        root.addLayout(header)
        root.addWidget(form)
        root.addStretch()

    def _current_member_id(self):
        if SessionManager is None:
            return None
        try:
            current_user = SessionManager.current_user()
            return None if current_user is None else getattr(current_user, "user_id", None)
        except Exception:
            return None

    def submit(self):
        success, message = self.service.submit_registration(
            visitor_name=self.name_input.text(),
            phone=self.phone_input.text(),
            patient_name=self.patient_input.text(),
            relation=self.relation_input.text(),
            purpose=self.purpose_input.text(),
            member_id=self._current_member_id(),
        )

        self.status_label.setText(message)
        self.status_label.setObjectName("chipGreen" if success else "chipRed")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        if success:
            self.name_input.clear()
            self.phone_input.clear()
            self.patient_input.clear()
            self.relation_input.clear()
            self.purpose_input.clear()
