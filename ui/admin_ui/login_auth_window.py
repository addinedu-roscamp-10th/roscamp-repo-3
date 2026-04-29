from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame
)
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from ui.utils.network.heartbeat import HeartbeatMonitor
from ui.utils.network.service_clients import LoginClient
from ui.utils.session.session_manager import SessionManager, UserSession


class LoginWorker(QObject):
    finished = pyqtSignal(bool, object)

    def __init__(self, login_id: str, password: str, role: str):
        super().__init__()
        self.login_id = login_id
        self.password = password
        self.role = role

    def run(self):
        try:
            ok, payload = LoginClient().authenticate(self.login_id, self.password, self.role)
            self.finished.emit(ok, payload)
        except Exception as exc:
            self.finished.emit(False, str(exc))


class LoginAuthWindow(QWidget):
    def __init__(self, role: str = "caregiver", previous_window=None):
        super().__init__()
        self.role = role
        self.previous_window = previous_window
        self.main_window = None
        self.login_btn = None
        self.login_thread = None
        self.login_worker = None
        self.inline_status = None
        self.status_text = None
        self.heartbeat = HeartbeatMonitor(parent=self)

        self.setWindowTitle("ROPI 요양보호사 로그인")
        self.resize(1120, 720)
        self._build_ui()
        self.heartbeat.status_changed.connect(self._update_server_status)
        self.heartbeat.start()

    def _build_ui(self):
        self.setObjectName("loginAuthRoot")

        root = QHBoxLayout(self)
        root.setContentsMargins(72, 56, 72, 56)
        root.setSpacing(36)

        hero = QFrame()
        hero.setObjectName("loginHeroPanel")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(34, 34, 34, 34)
        hero_layout.setSpacing(20)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)

        brand = QLabel("ROPI")
        brand.setObjectName("loginBrandTitle")

        brand_tag = QLabel("CARE OPERATIONS")
        brand_tag.setObjectName("loginBrandTag")

        brand_row.addWidget(brand)
        brand_row.addWidget(brand_tag)
        brand_row.addStretch()

        hero_title = QLabel("요양보호사 운영 콘솔")
        hero_title.setObjectName("loginHeroTitle")
        hero_title.setWordWrap(True)

        hero_description = QLabel(
            "로봇 작업 요청, 진행 상태, 재고와 어르신 정보를 한 화면에서 관리합니다."
        )
        hero_description.setObjectName("loginHeroDescription")
        hero_description.setWordWrap(True)

        feature_row = QHBoxLayout()
        feature_row.setSpacing(12)
        for title, desc in [
            ("작업 요청", "운반, 순찰, 안내 task 생성"),
            ("상태 확인", "로봇과 관제 서버 상태 추적"),
            ("운영 기록", "알림, 오류, 처리 결과 확인"),
        ]:
            feature = QFrame()
            feature.setObjectName("loginFeatureCard")
            feature_layout = QVBoxLayout(feature)
            feature_layout.setContentsMargins(16, 14, 16, 14)
            feature_layout.setSpacing(6)

            feature_title = QLabel(title)
            feature_title.setObjectName("loginFeatureTitle")
            feature_desc = QLabel(desc)
            feature_desc.setObjectName("loginFeatureDesc")
            feature_desc.setWordWrap(True)

            feature_layout.addWidget(feature_title)
            feature_layout.addWidget(feature_desc)
            feature_row.addWidget(feature)

        status_chip = QFrame()
        status_chip.setObjectName("loginStatusChip")
        status_layout = QHBoxLayout(status_chip)
        status_layout.setContentsMargins(14, 10, 14, 10)
        status_layout.setSpacing(10)

        status_label = QLabel("Control Service")
        status_label.setObjectName("loginStatusLabel")

        self.status_text = QLabel("관제 서버 확인 중")
        self.status_text.setObjectName("loginServerStatus")

        status_layout.addWidget(status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.status_text)

        hero_layout.addLayout(brand_row)
        hero_layout.addStretch()
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_description)
        hero_layout.addLayout(feature_row)
        hero_layout.addStretch()
        hero_layout.addWidget(status_chip)

        card_wrap = QVBoxLayout()
        card_wrap.setContentsMargins(0, 0, 0, 0)
        card_wrap.setSpacing(0)

        role_text = "요양보호사" if self.role == "caregiver" else "방문객"

        panel = QFrame()
        panel.setObjectName("loginCard")
        panel.setMaximumWidth(460)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(38, 36, 38, 36)
        panel_layout.setSpacing(14)

        title = QLabel(f"{role_text} 로그인")
        title.setObjectName("loginCardTitle")

        subtitle = QLabel("관리자 앱 사용을 위해 계정 정보를 입력하세요.")
        subtitle.setObjectName("loginCardSubtitle")
        subtitle.setWordWrap(True)

        id_label = QLabel("아이디")
        id_label.setObjectName("fieldLabel")
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText(f"{role_text} ID 입력")
        self.id_input.setObjectName("inputField")
        self.id_input.returnPressed.connect(self.handle_login)

        pw_label = QLabel("비밀번호")
        pw_label.setObjectName("fieldLabel")
        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("비밀번호 입력")
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setObjectName("inputField")
        self.pw_input.returnPressed.connect(self.handle_login)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.login_btn = QPushButton("로그인")
        self.login_btn.setObjectName("primaryButton")
        self.login_btn.clicked.connect(self.handle_login)

        if self.previous_window is not None:
            back_btn = QPushButton("뒤로가기")
            back_btn.setObjectName("secondaryButton")
            back_btn.clicked.connect(self.go_back)
            btn_row.addWidget(back_btn)
        btn_row.addWidget(self.login_btn)

        self.inline_status = QLabel(" ")
        self.inline_status.setObjectName("loginInlineStatus")
        self.inline_status.setProperty("state", "idle")
        self.inline_status.setWordWrap(True)

        panel_layout.addWidget(title)
        panel_layout.addWidget(subtitle)
        panel_layout.addSpacing(12)
        panel_layout.addWidget(id_label)
        panel_layout.addWidget(self.id_input)
        panel_layout.addWidget(pw_label)
        panel_layout.addWidget(self.pw_input)
        panel_layout.addWidget(self.inline_status)
        panel_layout.addSpacing(8)
        panel_layout.addLayout(btn_row)

        card_wrap.addStretch()
        card_wrap.addWidget(panel)
        card_wrap.addStretch()

        root.addWidget(hero, 3)
        root.addLayout(card_wrap, 2)

    def handle_login(self):
        login_id = self.id_input.text().strip()
        password = self.pw_input.text().strip()

        if not login_id or not password:
            self._set_inline_status("아이디와 비밀번호를 입력하세요.", "warning")
            return

        if self.login_thread is not None:
            return

        self._set_inline_status("로그인 요청 중입니다.", "info")
        self.login_btn.setEnabled(False)
        self.login_btn.setText("로그인 중...")
        self.id_input.setEnabled(False)
        self.pw_input.setEnabled(False)

        self.login_thread = QThread(self)
        self.login_worker = LoginWorker(login_id, password, self.role)
        self.login_worker.moveToThread(self.login_thread)
        self.login_thread.started.connect(self.login_worker.run)
        self.login_worker.finished.connect(self._handle_login_result)
        self.login_worker.finished.connect(self.login_thread.quit)
        self.login_worker.finished.connect(self.login_worker.deleteLater)
        self.login_thread.finished.connect(self.login_thread.deleteLater)
        self.login_thread.finished.connect(self._clear_login_thread)
        self.login_thread.start()

    def _handle_login_result(self, ok, payload):
        try:
            if not ok:
                self._set_inline_status(str(payload), "warning")
                return

            session_data = payload
            if session_data.get("role") != self.role:
                self._set_inline_status("로그인 역할이 현재 앱과 일치하지 않습니다.", "warning")
                return

            SessionManager.login(UserSession(
                user_id=session_data["user_id"],
                name=session_data["name"],
                role=session_data["role"]
            ))

            if session_data["role"] == "caregiver":
                from ui.admin_ui.main_window import CaregiverMainWindow
                self.main_window = CaregiverMainWindow()
            else:
                from ui.user_ui.main_window import VisitorMainWindow
                self.main_window = VisitorMainWindow()

            self.main_window.show()
            self.close()

        except Exception as e:
            self._set_inline_status(f"로그인 후 화면 전환 중 오류가 발생했습니다. {e}", "warning")

        finally:
            if self.isVisible():
                self.login_btn.setEnabled(True)
                self.login_btn.setText("로그인")
                self.id_input.setEnabled(True)
                self.pw_input.setEnabled(True)
            self._clear_login_thread()

    def _clear_login_thread(self):
        self.login_thread = None
        self.login_worker = None

    def _set_inline_status(self, message: str, state: str):
        if self.inline_status is None:
            return

        self.inline_status.setText(message)
        self.inline_status.setProperty("state", state)
        self.inline_status.style().unpolish(self.inline_status)
        self.inline_status.style().polish(self.inline_status)

    def _update_server_status(self, ok: bool, message: str):
        if self.status_text is None:
            return

        state = "online" if ok else "offline"
        prefix = "정상" if ok else "연결 실패"
        self.status_text.setText(f"{prefix} / {message}")
        self.status_text.setProperty("state", state)
        self.status_text.style().unpolish(self.status_text)
        self.status_text.style().polish(self.status_text)

    def go_back(self):
        if self.previous_window is not None:
            self.previous_window.show()
        self.close()

    def closeEvent(self, event):
        self.heartbeat.stop()
        super().closeEvent(event)
