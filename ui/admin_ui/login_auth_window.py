import json

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from ui.utils.network.service_clients import LoginClient
from ui.utils.network.tcp_client import TcpClientError
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
    def __init__(self, role: str, previous_window=None):
        super().__init__()
        self.role = role
        self.previous_window = previous_window
        self.main_window = None
        self.login_btn = None
        self.login_thread = None
        self.login_worker = None

        self.setWindowTitle("로그인")
        self.resize(640, 520)
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("loginAuthRoot")

        root = QVBoxLayout(self)
        root.setContentsMargins(48, 40, 48, 40)
        root.setSpacing(20)

        panel = QFrame()
        panel.setObjectName("glassPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(36, 36, 36, 36)
        panel_layout.setSpacing(18)

        role_text = "보호사" if self.role == "caregiver" else "방문객"

        title = QLabel(f"{role_text} 로그인")
        title.setObjectName("mainTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("아이디와 비밀번호를 입력해 주세요.")
        subtitle.setObjectName("subTitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        id_label = QLabel("아이디")
        id_label.setObjectName("fieldLabel")
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("아이디 입력")
        self.id_input.setObjectName("inputField")

        pw_label = QLabel("비밀번호")
        pw_label.setObjectName("fieldLabel")
        self.pw_input = QLineEdit()
        self.pw_input.setPlaceholderText("비밀번호 입력")
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setObjectName("inputField")

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        back_btn = QPushButton("뒤로가기")
        back_btn.setObjectName("secondaryButton")
        back_btn.clicked.connect(self.go_back)

        self.login_btn = QPushButton("로그인")
        self.login_btn.setObjectName("primaryButton")
        self.login_btn.clicked.connect(self.handle_login)

        btn_row.addWidget(back_btn)
        btn_row.addWidget(self.login_btn)

        panel_layout.addWidget(title)
        panel_layout.addWidget(subtitle)
        panel_layout.addSpacing(6)
        panel_layout.addWidget(id_label)
        panel_layout.addWidget(self.id_input)
        panel_layout.addWidget(pw_label)
        panel_layout.addWidget(self.pw_input)
        panel_layout.addSpacing(10)
        panel_layout.addLayout(btn_row)

        root.addStretch()
        root.addWidget(panel)
        root.addStretch()

    def handle_login(self):
        login_id = self.id_input.text().strip()
        password = self.pw_input.text().strip()

        if not login_id or not password:
            QMessageBox.warning(self, "입력 오류", "아이디와 비밀번호를 입력하세요.")
            return

        if self.login_thread is not None:
            return

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
                QMessageBox.warning(self, "로그인 실패", str(payload))
                return

            session_data = payload
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
            QMessageBox.critical(self, "오류", f"로그인 후 화면 전환 중 오류가 발생했습니다.\n{e}")

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

    def go_back(self):
        if self.previous_window is not None:
            self.previous_window.show()
        self.close()
