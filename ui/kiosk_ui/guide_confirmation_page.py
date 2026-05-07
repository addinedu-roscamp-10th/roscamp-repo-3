from uuid import uuid4

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.kiosk_ui.shared_widgets import KioskResidentPersonIcon
from ui.utils.network.service_clients import VisitGuideRemoteService


class KioskTopIconButton(QPushButton):
    def __init__(self, icon_name):
        super().__init__("")
        self.icon_name = icon_name
        self.setObjectName("kioskTopIconButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(72, 72)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor("#2F855A" if self.icon_name == "arrow_back" else "#64748B")
        pen = QPen(color, 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        center_x = int(self.width() / 2)
        center_y = int(self.height() / 2)
        if self.icon_name == "arrow_back":
            painter.drawLine(center_x + 14, center_y, center_x - 14, center_y)
            painter.drawLine(center_x - 14, center_y, center_x - 3, center_y - 11)
            painter.drawLine(center_x - 14, center_y, center_x - 3, center_y + 11)
            return

        painter.drawLine(center_x - 15, center_y - 3, center_x, center_y - 17)
        painter.drawLine(center_x, center_y - 17, center_x + 15, center_y - 3)
        painter.drawRoundedRect(QRectF(center_x - 11, center_y - 3, 22, 20), 3, 3)
        painter.drawLine(center_x - 3, center_y + 17, center_x - 3, center_y + 6)
        painter.drawLine(center_x + 3, center_y + 6, center_x + 3, center_y + 17)


class KioskGuideNoticeGlyph(QWidget):
    def __init__(self, icon_name, *, object_name="kioskGuideNoticeLineIcon"):
        super().__init__()
        self.icon_name = icon_name
        self.setObjectName(object_name)
        self.setFixedSize(44, 44)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.icon_name == "info":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#2B6CB0")))
            painter.drawEllipse(QRectF(4, 4, 36, 36))
            pen = QPen(QColor("#FFFFFF"), 4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPoint(22, 15)
            painter.drawLine(22, 22, 22, 31)
            return

        pen = QPen(QColor("#2B6CB0"), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.icon_name == "walk":
            painter.drawEllipse(QRectF(17, 4, 10, 10))
            painter.drawLine(22, 16, 22, 27)
            painter.drawLine(22, 20, 13, 25)
            painter.drawLine(22, 27, 13, 38)
            painter.drawLine(22, 27, 33, 38)
            painter.drawLine(22, 19, 32, 22)
        elif self.icon_name == "obstacle":
            painter.drawRoundedRect(QRectF(8, 9, 28, 20), 5, 5)
            painter.drawLine(14, 35, 30, 35)
            painter.drawLine(16, 29, 12, 35)
            painter.drawLine(28, 29, 32, 35)
            painter.drawPoint(17, 19)
            painter.drawPoint(27, 19)
        else:
            painter.drawRoundedRect(QRectF(9, 8, 26, 26), 7, 7)
            painter.drawLine(22, 15, 22, 27)
            painter.drawLine(16, 21, 28, 21)
            painter.drawLine(15, 36, 29, 36)


class KioskConfirmationActionButton(QPushButton):
    def __init__(self, text, icon_name):
        super().__init__(text)
        self.icon_name = icon_name
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor("#FFFFFF" if self.icon_name == "play" else "#B9472B")
        pen = QPen(color, 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        text_width = self.fontMetrics().horizontalAdvance(self.text())
        icon_center_x = int(self.width() / 2 - text_width / 2 - 34)
        icon_center_y = int(self.height() / 2)
        if self.icon_name == "play":
            painter.setBrush(QBrush(color))
            path = QPainterPath()
            path.moveTo(icon_center_x - 6, icon_center_y - 14)
            path.lineTo(icon_center_x + 14, icon_center_y)
            path.lineTo(icon_center_x - 6, icon_center_y + 14)
            path.closeSubpath()
            painter.drawPath(path)
            return

        painter.drawEllipse(QRectF(icon_center_x - 10, icon_center_y - 18, 20, 20))
        painter.drawArc(
            QRectF(icon_center_x - 17, icon_center_y - 1, 34, 28),
            25 * 16,
            130 * 16,
        )
        painter.drawLine(
            icon_center_x + 15,
            icon_center_y - 5,
            icon_center_x + 23,
            icon_center_y - 12,
        )
        painter.drawLine(
            icon_center_x - 15,
            icon_center_y - 5,
            icon_center_x - 23,
            icon_center_y - 12,
        )


class KioskGuideConfirmationPage(QWidget):
    def __init__(self, *, go_home_page=None, go_back_page=None, go_progress_page=None):
        super().__init__()
        self.setObjectName("kioskGuideConfirmationPage")
        self.go_home_page = go_home_page
        self.go_back_page = go_back_page
        self.go_progress_page = go_progress_page
        self.service = VisitGuideRemoteService()
        self.selected_patient = None
        self.current_session = None
        self.detected_target_track_id = None
        self._guide_request_id = None
        self._guide_idempotency_key = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = QFrame()
        self.top_bar.setObjectName("kioskConfirmationTopBar")
        self.top_bar.setFixedHeight(96)
        header_layout = QHBoxLayout(self.top_bar)
        header_layout.setContentsMargins(64, 12, 64, 12)
        header_layout.setSpacing(12)

        self.back_button = KioskTopIconButton("arrow_back")
        self.back_button.clicked.connect(self._go_back)

        brand = QLabel("ROPI")
        brand.setObjectName("kioskConfirmationBrand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.home_button = KioskTopIconButton("home")
        self.home_button.clicked.connect(self._go_home)

        header_layout.addWidget(self.back_button)
        header_layout.addStretch()
        header_layout.addWidget(brand)
        header_layout.addStretch()
        header_layout.addWidget(self.home_button)

        page_shell = QVBoxLayout()
        page_shell.setContentsMargins(64, 32, 64, 0)
        page_shell.setSpacing(28)
        page_shell.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("kioskConfirmationSummaryCard")
        self.summary_card.setMinimumHeight(190)
        self.summary_card.setMinimumWidth(860)
        self.summary_card.setMaximumWidth(960)
        self.summary_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(32, 24, 32, 24)
        summary_layout.setSpacing(12)
        summary_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        summary_icon_wrap = QFrame()
        summary_icon_wrap.setObjectName("kioskConfirmationPersonBubble")
        summary_icon_wrap.setFixedSize(80, 80)
        summary_icon_layout = QVBoxLayout(summary_icon_wrap)
        summary_icon_layout.setContentsMargins(0, 0, 0, 0)
        summary_icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_icon_layout.addWidget(KioskResidentPersonIcon())

        self.summary_title = QLabel("어르신을 선택해 주세요")
        self.summary_title.setObjectName("kioskConfirmationTitle")
        self.summary_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_title.setMinimumHeight(48)

        self.summary_subtitle = QLabel("안내를 시작하시겠습니까?")
        self.summary_subtitle.setObjectName("kioskConfirmationSubtitle")
        self.summary_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary_subtitle.setMinimumHeight(32)

        summary_layout.addWidget(summary_icon_wrap, alignment=Qt.AlignmentFlag.AlignHCenter)
        summary_layout.addWidget(self.summary_title)
        summary_layout.addWidget(self.summary_subtitle)

        self.robot_status_card = QFrame()
        self.robot_status_card.setObjectName("kioskConfirmationStatusCard")
        self.robot_status_card.setMinimumHeight(96)
        self.robot_status_card.setMinimumWidth(860)
        self.robot_status_card.setMaximumWidth(960)
        self.robot_status_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        robot_layout = QHBoxLayout(self.robot_status_card)
        robot_layout.setContentsMargins(28, 18, 28, 18)
        robot_layout.setSpacing(20)

        ready_chip = QLabel("준비 완료")
        ready_chip.setObjectName("kioskReadyChip")
        ready_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ready_chip.setMinimumHeight(44)

        self.robot_status_text = QLabel("안내 로봇 [ROPI-01]이 대기 중입니다.")
        self.robot_status_text.setObjectName("kioskRobotStatusText")
        self.robot_status_text.setWordWrap(True)

        robot_layout.addWidget(ready_chip, alignment=Qt.AlignmentFlag.AlignVCenter)
        robot_layout.addWidget(self.robot_status_text, 1)

        self.notice_card = QFrame()
        self.notice_card.setObjectName("kioskGuideNoticeCard")
        self.notice_card.setMinimumHeight(284)
        self.notice_card.setMinimumWidth(860)
        self.notice_card.setMaximumWidth(960)
        self.notice_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        notice_layout = QVBoxLayout(self.notice_card)
        notice_layout.setContentsMargins(0, 0, 0, 0)
        notice_layout.setSpacing(0)

        self.notice_header = QFrame()
        self.notice_header.setObjectName("kioskGuideNoticeHeader")
        self.notice_header.setFixedHeight(72)
        notice_header_layout = QHBoxLayout(self.notice_header)
        notice_header_layout.setContentsMargins(20, 16, 20, 16)
        notice_header_layout.setSpacing(12)

        self.notice_header_icon = KioskGuideNoticeGlyph(
            "info",
            object_name="kioskGuideNoticeHeaderIcon",
        )

        notice_header_title = QLabel("안내 시 주의사항")
        notice_header_title.setObjectName("kioskGuideNoticeHeaderTitle")
        notice_header_title.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        notice_header_layout.addStretch()
        notice_header_layout.addWidget(self.notice_header_icon)
        notice_header_layout.addWidget(notice_header_title)
        notice_header_layout.addStretch()

        notice_body = QFrame()
        notice_body.setObjectName("kioskGuideNoticeBody")
        notice_body_layout = QVBoxLayout(notice_body)
        notice_body_layout.setContentsMargins(32, 22, 32, 22)
        notice_body_layout.setSpacing(16)

        self.notice_rows = []
        for icon_name, text in [
            ("walk", "1. 로봇의 보폭에 맞춰 천천히 따라와 주세요."),
            ("obstacle", "2. 로봇 앞에 장애물이 있으면 멈출 수 있습니다."),
            ("help", "3. 도움이 필요하면 직원 호출 버튼을 눌러 주세요."),
        ]:
            row = QFrame()
            row.setObjectName("kioskGuideNoticeRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(16)
            icon = KioskGuideNoticeGlyph(icon_name)
            line = QLabel(text)
            line.setObjectName("kioskGuideNoticeLine")
            line.setWordWrap(True)
            line.setMinimumHeight(32)
            row_layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)
            row_layout.addWidget(line, 1)
            notice_body_layout.addWidget(row)
            self.notice_rows.append(row)

        notice_layout.addWidget(self.notice_header)
        notice_layout.addWidget(notice_body)

        self.inline_status = QLabel("안내 시작을 누르면 로봇 안내 요청이 접수됩니다.")
        self.inline_status.setObjectName("kioskStatusText")
        self.inline_status.setWordWrap(True)
        self.inline_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.inline_status.setMaximumWidth(960)
        self.inline_status.setHidden(True)

        page_shell.addWidget(self.summary_card, alignment=Qt.AlignmentFlag.AlignHCenter)
        page_shell.addWidget(self.robot_status_card, alignment=Qt.AlignmentFlag.AlignHCenter)
        page_shell.addWidget(self.notice_card, alignment=Qt.AlignmentFlag.AlignHCenter)
        page_shell.addWidget(self.inline_status, alignment=Qt.AlignmentFlag.AlignHCenter)
        page_shell.addStretch()

        bottom_bar = QFrame()
        bottom_bar.setObjectName("kioskConfirmationBottomBar")
        bottom_bar.setFixedHeight(120)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(64, 20, 64, 20)
        bottom_layout.setSpacing(24)

        self.confirm_button = KioskConfirmationActionButton("안내 시작", "play")
        self.confirm_button.setObjectName("kioskConfirmationPrimaryButton")
        self.confirm_button.setFixedHeight(80)
        self.confirm_button.setMaximumWidth(420)
        self.confirm_button.setEnabled(False)
        self.confirm_button.clicked.connect(self.confirm_guidance)

        self.call_staff_button = KioskConfirmationActionButton("직원 호출", "support")
        self.call_staff_button.setObjectName("kioskConfirmationSecondaryButton")
        self.call_staff_button.setFixedHeight(80)
        self.call_staff_button.setMaximumWidth(420)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.confirm_button, 1)
        bottom_layout.addWidget(self.call_staff_button, 1)
        bottom_layout.addStretch()

        root.addWidget(self.top_bar)
        root.addLayout(page_shell, 1)
        root.addWidget(bottom_bar)

    def set_patient(self, patient):
        self.selected_patient = patient or None
        self.current_session = None
        self._guide_request_id = None
        self._guide_idempotency_key = None
        if not self.selected_patient:
            self.summary_title.setText("어르신을 선택해 주세요")
            self.summary_subtitle.setText("안내를 시작하시겠습니까?")
            self.confirm_button.setEnabled(False)
            self.inline_status.setHidden(True)
            return

        name = str(self.selected_patient.get("name", "-")).strip() or "-"
        room = str(self.selected_patient.get("room", "-")).strip() or "-"
        self.summary_title.setText(f"{name} 어르신 ({self._format_room_label(room)})")
        self.summary_subtitle.setText("안내를 시작하시겠습니까?")
        self.confirm_button.setEnabled(bool(self.selected_patient.get("guide_available", True)))
        self.inline_status.setHidden(True)

    def confirm_guidance(self):
        if not self.selected_patient:
            self.inline_status.setText("방문 등록 후 안내를 시작할 수 있습니다.")
            self.inline_status.setHidden(False)
            return

        visitor_id = self._visitor_id()
        if visitor_id is None:
            self.inline_status.setText("방문 등록 정보가 없어 안내를 시작할 수 없습니다.")
            self.inline_status.setHidden(False)
            return

        try:
            guide_task = self.service.create_guide_task(
                request_id=self._current_guide_request_id(),
                visitor_id=visitor_id,
                idempotency_key=self._current_guide_idempotency_key(),
            )
        except Exception as exc:
            self.inline_status.setText(f"안내 시작 중 오류가 발생했습니다: {exc}")
            self.inline_status.setHidden(False)
            return

        if guide_task.get("result_code") != "ACCEPTED":
            self.inline_status.setText(
                guide_task.get("result_message") or "안내 요청이 거부되었습니다."
            )
            self.inline_status.setHidden(False)
            return

        try:
            command_success, message, command_response = self.service.send_guide_command(
                task_id=guide_task.get("task_id"),
                pinky_id=guide_task.get("assigned_robot_id"),
                command_type="WAIT_TARGET_TRACKING",
            )
        except Exception as exc:
            command_success = False
            message = f"로봇 호출 명령을 보낼 수 없습니다: {exc}"
            command_response = {
                "accepted": False,
                "reason_code": "GUIDE_COMMAND_ERROR",
                "result_message": message,
            }

        session = {
            **guide_task,
            "pinky_id": guide_task.get("assigned_robot_id"),
            "command_type": "WAIT_TARGET_TRACKING",
            "command_result_code": "COMMAND_ACCEPTED" if command_success else "COMMAND_FAILED",
            "command_message": message,
            "command_response": command_response,
        }
        if self.selected_patient:
            self.current_session = session
            name = self.selected_patient.get("name", "-")
            room = self.selected_patient.get("room", "-")
            task_id = str(session.get("task_id", "-")).strip() or "-"
            status_message = (
                f"{name} 어르신 안내 요청이 접수되었습니다. {room} 방향 대상 추적을 준비합니다."
                if command_success
                else f"{name} 어르신 안내 요청은 접수되었습니다. 로봇 호출 상태를 확인 중입니다."
            )
            self.inline_status.setText(f"{status_message} (task_id={task_id})")
            if self.go_progress_page:
                self.go_progress_page(self.selected_patient, session)
            return

    def _visitor_id(self):
        raw = (self.selected_patient or {}).get("visitor_id")
        try:
            visitor_id = int(raw)
        except (TypeError, ValueError):
            return None
        if visitor_id <= 0:
            return None
        return visitor_id

    def _current_guide_request_id(self):
        if self._guide_request_id is None:
            self._guide_request_id = f"kiosk_guide_{uuid4().hex}"
        return self._guide_request_id

    def _current_guide_idempotency_key(self):
        if self._guide_idempotency_key is None:
            self._guide_idempotency_key = f"idem_{self._current_guide_request_id()}"
        return self._guide_idempotency_key

    @staticmethod
    def _format_room_label(room):
        normalized = str(room or "-").strip() or "-"
        if normalized == "-":
            return normalized
        if normalized.endswith("호"):
            return normalized
        return f"{normalized}호"

    def _go_home(self):
        if self.go_home_page:
            self.go_home_page()

    def _go_back(self):
        if self.go_back_page:
            self.go_back_page()


__all__ = [
    "KioskConfirmationActionButton",
    "KioskGuideConfirmationPage",
    "KioskGuideNoticeGlyph",
    "KioskTopIconButton",
]
