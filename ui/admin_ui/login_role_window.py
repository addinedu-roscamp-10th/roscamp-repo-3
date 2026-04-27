from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame
)
from PyQt6.QtCore import Qt
from ui.utils.network.heartbeat import HeartbeatMonitor
from ui.admin_ui.login_auth_window import LoginAuthWindow


class LoginRoleWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.auth_window = None
        self.heartbeat = HeartbeatMonitor(parent=self)
        self.status_text = None
        self.setObjectName("loginRoleRoot")
        self.setWindowTitle("Care Robot System")
        self.resize(1200, 760)
        self._build_ui()
        self.heartbeat.status_changed.connect(self._update_server_status)
        self.heartbeat.start()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 36, 48, 36)
        root.setSpacing(24)

        panel = QFrame()
        panel.setObjectName("glassPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(45, 36, 42, 36)
        panel_layout.setSpacing(28)

        top_row = QHBoxLayout()

        badge = QLabel("Care Robot System")
        badge.setObjectName("badgeLabel")

        status_wrap = QHBoxLayout()
        status_wrap.setSpacing(10)

        wifi_icon = QLabel("📶")
        wifi_icon.setObjectName("wifiIcon")

        self.status_text = QLabel("메인 서버 연결 확인 중...")
        self.status_text.setObjectName("topStatusText")

        status_wrap.addWidget(wifi_icon)
        status_wrap.addWidget(self.status_text)

        top_row.addWidget(badge)
        top_row.addStretch()
        top_row.addLayout(status_wrap)

        title = QLabel("Welcome to ROPI")
        title.setObjectName("mainTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("이용할 사용자 유형을 선택한 뒤 로그인하세요.")
        subtitle.setObjectName("subTitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_row = QHBoxLayout()
        card_row.setSpacing(24)

        caregiver_btn = QPushButton(
            "👩‍⚕️  보호사 로그인\n\n로봇 호출, 작업 요청, 상태 조회,\n어르신 정보 및 오류 확인"
        )
        caregiver_btn.setObjectName("cardButtonBlue")
        caregiver_btn.setMinimumHeight(180)
        caregiver_btn.clicked.connect(lambda: self.open_auth("caregiver"))

        visitor_btn = QPushButton(
            "🧑‍🤝‍🧑  방문객 로그인\n\n방문 등록, 어르신에게 가이드,\n직원 호출 기능 사용"
        )
        visitor_btn.setObjectName("cardButtonGreen")
        visitor_btn.setMinimumHeight(180)
        visitor_btn.clicked.connect(lambda: self.open_auth("visitor"))

        card_row.addWidget(caregiver_btn)
        card_row.addWidget(visitor_btn)

        panel_layout.addLayout(top_row)
        panel_layout.addWidget(title)
        panel_layout.addWidget(subtitle)
        panel_layout.addLayout(card_row)

        root.addStretch()
        root.addWidget(panel)
        root.addStretch()

    def open_auth(self, role: str):
        self.auth_window = LoginAuthWindow(role=role, previous_window=self)
        self.auth_window.show()
        self.hide()

    def _update_server_status(self, ok: bool, message: str):
        if self.status_text is None:
            return

        prefix = "메인 서버 정상" if ok else "메인 서버 연결 실패"
        self.status_text.setText(f"{prefix} / {message}")
