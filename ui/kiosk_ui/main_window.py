import sys
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.utils.core.styles import load_stylesheet
from ui.utils.network.service_clients import VisitGuideRemoteService


class KioskHomeActionCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, *, accent, icon_text, title_text, desc_text):
        super().__init__()
        self.setObjectName("kioskActionCard")
        self.setProperty("accent", accent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        self.accent_bar = QFrame()
        self.accent_bar.setObjectName("kioskCardAccent")
        self.accent_bar.setProperty("accent", accent)
        self.accent_bar.setFixedHeight(8)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("kioskIconBubble")
        icon_wrap.setProperty("accent", accent)
        icon_wrap.setFixedSize(116, 116)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon = QLabel(icon_text)
        self.icon.setObjectName("kioskActionIcon")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(self.icon)

        self.title = QLabel(title_text)
        self.title.setObjectName("kioskActionTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.desc = QLabel(desc_text)
        self.desc.setObjectName("kioskActionDesc")
        self.desc.setWordWrap(True)
        self.desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.cta = QPushButton("선택")
        self.cta.setObjectName("kioskGhostButton")
        self.cta.setProperty("accent", accent)
        self.cta.setMinimumHeight(56)

        layout.addWidget(self.accent_bar)
        layout.addSpacing(4)
        layout.addWidget(icon_wrap, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.desc)
        layout.addStretch()
        layout.addWidget(self.cta)

        self.cta.clicked.connect(self.clicked.emit)
        for widget in [self.icon, self.title, self.desc]:
            widget.mousePressEvent = self._child_click

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _child_click(self, event):
        self.clicked.emit()


class KioskFooterStat(QFrame):
    def __init__(self, *, icon_text, title_text, value_text):
        super().__init__()
        self.setObjectName("kioskFooterStat")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(14)

        icon = QLabel(icon_text)
        icon.setObjectName("kioskFooterIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedWidth(34)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(2)

        title = QLabel(title_text)
        title.setObjectName("kioskFooterLabel")

        value = QLabel(value_text)
        value.setObjectName("kioskFooterValue")

        text_wrap.addWidget(title)
        text_wrap.addWidget(value)

        layout.addWidget(icon)
        layout.addLayout(text_wrap)


class KioskResidentSearchPage(QWidget):
    def __init__(self, *, go_home_page=None, go_confirmation_page=None, go_back_page=None):
        super().__init__()
        self.go_home_page = go_home_page
        self.go_confirmation_page = go_confirmation_page
        self.go_back_page = go_back_page
        self.service = VisitGuideRemoteService()
        self.selected_patient = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("kioskSearchTopBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(56, 28, 56, 28)
        header_layout.setSpacing(18)

        brand_wrap = QHBoxLayout()
        brand_wrap.setSpacing(14)
        brand_wrap.setContentsMargins(0, 0, 0, 0)

        brand_icon = QLabel("✚")
        brand_icon.setObjectName("kioskBrandIcon")

        brand = QLabel("ROPI 요양보호 서비스")
        brand.setObjectName("kioskSearchBrand")

        brand_wrap.addWidget(brand_icon)
        brand_wrap.addWidget(brand)
        header_layout.addStretch()
        header_layout.addLayout(brand_wrap)
        header_layout.addStretch()

        self.call_staff_button = QPushButton("직원 호출")
        self.call_staff_button.setObjectName("kioskSearchCallButton")
        self.call_staff_button.setMinimumHeight(64)

        header_layout.addWidget(self.call_staff_button)

        page_shell = QVBoxLayout()
        page_shell.setContentsMargins(56, 32, 56, 0)
        page_shell.setSpacing(24)
        page_shell.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("어르신 찾기")
        title.setObjectName("kioskSearchPageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("방 번호나 성함을 입력해 주세요.")
        subtitle.setObjectName("kioskSearchPageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        search_card = QFrame()
        search_card.setObjectName("kioskSearchInputCard")
        search_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        search_card.setFixedHeight(76)
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("kioskSearchInput")
        self.search_input.setPlaceholderText("예: 302호 또는 김철수")
        self.search_input.returnPressed.connect(self.search_patient)

        self.search_button = QPushButton("찾기")
        self.search_button.setObjectName("kioskSearchSubmitButton")
        self.search_button.setMinimumHeight(72)
        self.search_button.clicked.connect(self.search_patient)

        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.search_button)

        self.status_label = QLabel("어르신을 검색하면 결과가 이곳에 표시됩니다.")
        self.status_label.setObjectName("kioskSearchStatusText")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.result_card = QFrame()
        self.result_card.setObjectName("kioskResidentResultCard")
        self.result_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.result_card.setMinimumHeight(150)
        result_layout = QHBoxLayout(self.result_card)
        result_layout.setContentsMargins(24, 24, 24, 24)
        result_layout.setSpacing(18)

        avatar = QFrame()
        avatar.setObjectName("kioskResidentAvatar")
        avatar.setFixedSize(84, 84)
        avatar_layout = QVBoxLayout(avatar)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        avatar_icon = QLabel("◉")
        avatar_icon.setObjectName("kioskResidentAvatarIcon")
        avatar_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_layout.addWidget(avatar_icon)

        info_wrap = QVBoxLayout()
        info_wrap.setSpacing(6)

        self.name_label = QLabel("검색 결과가 없습니다")
        self.name_label.setObjectName("kioskResidentName")

        self.room_label = QLabel("병실: -")
        self.room_label.setObjectName("kioskResidentRoom")

        self.location_label = QLabel("위치: -")
        self.location_label.setObjectName("kioskResidentMeta")

        self.visit_label = QLabel("면회 상태: -")
        self.visit_label.setObjectName("kioskResidentMeta")

        info_wrap.addWidget(self.name_label)
        info_wrap.addWidget(self.room_label)
        info_wrap.addWidget(self.location_label)
        info_wrap.addWidget(self.visit_label)

        self.start_button = QPushButton("안내 시작")
        self.start_button.setObjectName("kioskResidentActionButton")
        self.start_button.setMinimumHeight(72)
        self.start_button.clicked.connect(self.start_guidance)

        result_layout.addWidget(avatar)
        result_layout.addLayout(info_wrap, 1)
        result_layout.addWidget(self.start_button)

        page_shell.addWidget(header)
        page_shell.addWidget(title)
        page_shell.addWidget(subtitle)
        page_shell.addWidget(search_card)
        page_shell.addWidget(self.result_card)
        page_shell.addWidget(self.status_label)

        bottom_bar = QFrame()
        bottom_bar.setObjectName("kioskSearchBottomBar")
        action_row = QHBoxLayout(bottom_bar)
        action_row.setContentsMargins(56, 20, 56, 20)
        action_row.setSpacing(24)

        self.back_button = QPushButton("이전")
        self.back_button.setObjectName("kioskSearchFooterButton")
        self.back_button.setMinimumHeight(72)
        self.back_button.clicked.connect(self._go_back)

        self.home_button = QPushButton("처음으로")
        self.home_button.setObjectName("kioskSearchFooterButton")
        self.home_button.setMinimumHeight(72)
        self.home_button.clicked.connect(self._go_home)

        action_row.addWidget(self.back_button)
        action_row.addStretch()
        action_row.addWidget(self.home_button)

        root.addLayout(page_shell, 1)
        root.addWidget(bottom_bar)

    def search_patient(self):
        try:
            ok, message, patient = self.service.search_patient(self.search_input.text())
        except Exception as exc:
            self.selected_patient = None
            self._clear_result()
            self.status_label.setText(f"검색 중 오류가 발생했습니다: {exc}")
            return

        self.selected_patient = patient if ok else None
        if not ok:
            self._clear_result()
            self.status_label.setText(message)
            return

        self.name_label.setText(f"{patient.get('name', '-')} 어르신")
        self.room_label.setText(f"{patient.get('room', '-')}호")
        self.location_label.setText(f"위치: {patient.get('location', '-')}")
        self.visit_label.setText(f"면회 상태: {patient.get('status', '-')}")
        self.status_label.setText("검색 결과를 확인했습니다. 안내가 필요하면 안내 시작을 눌러주세요.")

    def start_guidance(self):
        if not self.selected_patient:
            self.status_label.setText("먼저 어르신을 검색해 주세요.")
            return

        if self.go_confirmation_page:
            self.go_confirmation_page(self.selected_patient)
            return

        self.status_label.setText("안내 확인 화면으로 이동할 수 없습니다.")

    def reset_search(self):
        self.search_input.clear()
        self.selected_patient = None
        self._clear_result()
        self.status_label.setText("어르신을 검색하면 결과가 이곳에 표시됩니다.")

    def _clear_result(self):
        self.name_label.setText("검색 결과가 없습니다")
        self.room_label.setText("병실: -")
        self.location_label.setText("위치: -")
        self.visit_label.setText("면회 상태: -")

    def _go_home(self):
        if self.go_home_page:
            self.go_home_page()

    def _go_back(self):
        if self.go_back_page:
            self.go_back_page()
            return
        self._go_home()


class KioskGuideConfirmationPage(QWidget):
    def __init__(self, *, go_home_page=None, go_back_page=None, go_progress_page=None):
        super().__init__()
        self.go_home_page = go_home_page
        self.go_back_page = go_back_page
        self.go_progress_page = go_progress_page
        self.service = VisitGuideRemoteService()
        self.selected_patient = None
        self.current_session = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        page_shell = QVBoxLayout()
        page_shell.setContentsMargins(56, 24, 56, 0)
        page_shell.setSpacing(28)

        header = QFrame()
        header.setObjectName("kioskConfirmationTopBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        self.back_button = QPushButton("뒤로")
        self.back_button.setObjectName("kioskRoundIconButton")
        self.back_button.setMinimumSize(72, 72)
        self.back_button.clicked.connect(self._go_back)

        brand = QLabel("ROPI")
        brand.setObjectName("kioskConfirmationBrand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.home_button = QPushButton("홈")
        self.home_button.setObjectName("kioskRoundIconButton")
        self.home_button.setMinimumSize(72, 72)
        self.home_button.clicked.connect(self._go_home)

        header_layout.addWidget(self.back_button)
        header_layout.addStretch()
        header_layout.addWidget(brand)
        header_layout.addStretch()
        header_layout.addWidget(self.home_button)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("kioskConfirmationSummaryCard")
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(28, 28, 28, 28)
        summary_layout.setSpacing(10)
        summary_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        summary_icon = QLabel("○")
        summary_icon.setObjectName("kioskConfirmationSummaryIcon")
        summary_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.summary_title = QLabel("어르신을 선택해 주세요")
        self.summary_title.setObjectName("kioskConfirmationTitle")
        self.summary_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.summary_subtitle = QLabel("안내를 시작하시겠습니까?")
        self.summary_subtitle.setObjectName("kioskConfirmationSubtitle")
        self.summary_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        summary_layout.addWidget(summary_icon)
        summary_layout.addWidget(self.summary_title)
        summary_layout.addWidget(self.summary_subtitle)

        self.robot_status_card = QFrame()
        self.robot_status_card.setObjectName("kioskConfirmationStatusCard")
        robot_layout = QHBoxLayout(self.robot_status_card)
        robot_layout.setContentsMargins(24, 22, 24, 22)
        robot_layout.setSpacing(18)

        ready_chip = QLabel("준비 완료")
        ready_chip.setObjectName("kioskReadyChip")

        self.robot_status_text = QLabel("안내 로봇 [ROPI-01]이 대기 중입니다.")
        self.robot_status_text.setObjectName("kioskRobotStatusText")
        self.robot_status_text.setWordWrap(True)

        robot_layout.addWidget(ready_chip, alignment=Qt.AlignmentFlag.AlignVCenter)
        robot_layout.addWidget(self.robot_status_text, 1)

        self.notice_card = QFrame()
        self.notice_card.setObjectName("kioskGuideNoticeCard")
        notice_layout = QVBoxLayout(self.notice_card)
        notice_layout.setContentsMargins(0, 0, 0, 0)
        notice_layout.setSpacing(0)

        notice_header = QFrame()
        notice_header.setObjectName("kioskGuideNoticeHeader")
        notice_header_layout = QHBoxLayout(notice_header)
        notice_header_layout.setContentsMargins(20, 16, 20, 16)
        notice_header_layout.setSpacing(10)

        notice_header_icon = QLabel("i")
        notice_header_icon.setObjectName("kioskGuideNoticeHeaderIcon")

        notice_header_title = QLabel("안내 시 주의사항")
        notice_header_title.setObjectName("kioskGuideNoticeHeaderTitle")

        notice_header_layout.addStretch()
        notice_header_layout.addWidget(notice_header_icon)
        notice_header_layout.addWidget(notice_header_title)
        notice_header_layout.addStretch()

        notice_body = QFrame()
        notice_body.setObjectName("kioskGuideNoticeBody")
        notice_body_layout = QVBoxLayout(notice_body)
        notice_body_layout.setContentsMargins(28, 24, 28, 24)
        notice_body_layout.setSpacing(18)

        for text in [
            "1. 로봇의 이동 속도에 맞춰 천천히 따라와 주세요.",
            "2. 로봇 앞에 사람이 많거나 장애물이 있으면 잠시 멈출 수 있습니다.",
            "3. 도움이 필요하면 직원 호출을 눌러 바로 도움을 요청해 주세요.",
        ]:
            line = QLabel(text)
            line.setObjectName("kioskGuideNoticeLine")
            line.setWordWrap(True)
            notice_body_layout.addWidget(line)

        notice_layout.addWidget(notice_header)
        notice_layout.addWidget(notice_body)

        self.inline_status = QLabel("안내 시작을 누르면 로봇 안내 요청이 접수됩니다.")
        self.inline_status.setObjectName("kioskStatusText")
        self.inline_status.setWordWrap(True)
        self.inline_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        page_shell.addWidget(header)
        page_shell.addWidget(self.summary_card)
        page_shell.addWidget(self.robot_status_card)
        page_shell.addWidget(self.notice_card, 1)
        page_shell.addWidget(self.inline_status)

        bottom_bar = QFrame()
        bottom_bar.setObjectName("kioskConfirmationBottomBar")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(56, 20, 56, 20)
        bottom_layout.setSpacing(24)

        self.confirm_button = QPushButton("안내 시작")
        self.confirm_button.setObjectName("kioskConfirmationPrimaryButton")
        self.confirm_button.setMinimumHeight(80)
        self.confirm_button.clicked.connect(self.confirm_guidance)

        self.call_staff_button = QPushButton("직원 호출")
        self.call_staff_button.setObjectName("kioskConfirmationSecondaryButton")
        self.call_staff_button.setMinimumHeight(80)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.confirm_button, 1)
        bottom_layout.addWidget(self.call_staff_button, 1)
        bottom_layout.addStretch()

        root.addLayout(page_shell, 1)
        root.addWidget(bottom_bar)

    def set_patient(self, patient):
        self.selected_patient = patient or None
        self.current_session = None
        if not self.selected_patient:
            self.summary_title.setText("어르신을 선택해 주세요")
            self.summary_subtitle.setText("안내를 시작하시겠습니까?")
            return

        name = str(self.selected_patient.get("name", "-")).strip() or "-"
        room = str(self.selected_patient.get("room", "-")).strip() or "-"
        self.summary_title.setText(f"{name} 어르신 ({room})")
        self.summary_subtitle.setText("안내를 시작하시겠습니까?")
        self.inline_status.setText("안내 시작을 누르면 로봇 안내 요청이 접수됩니다.")

    def confirm_guidance(self):
        try:
            success, message, session = self.service.begin_guide_session(
                patient=self.selected_patient,
                command_type="WAIT_TARGET_TRACKING",
            )
        except Exception as exc:
            self.inline_status.setText(f"안내 시작 중 오류가 발생했습니다: {exc}")
            return

        if success and self.selected_patient and session:
            self.current_session = session
            name = self.selected_patient.get("name", "-")
            room = self.selected_patient.get("room", "-")
            task_id = str(session.get("task_id", "-")).strip() or "-"
            self.inline_status.setText(
                f"{name} 어르신 안내 요청이 접수되었습니다. {room} 방향 대상 추적을 준비합니다. "
                f"(task_id={task_id})"
            )
            if self.go_progress_page:
                self.go_progress_page(self.selected_patient, session)
            return

        self.inline_status.setText(message)

    def _go_home(self):
        if self.go_home_page:
            self.go_home_page()

    def _go_back(self):
        if self.go_back_page:
            self.go_back_page()


class KioskProgressStage(QFrame):
    def __init__(self, *, title_text, active=False, completed=False):
        super().__init__()
        self.setObjectName("kioskProgressStage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel("●" if (active or completed) else "○")
        badge.setObjectName("kioskProgressStageBadge")
        if active:
            badge.setProperty("state", "active")
        elif completed:
            badge.setProperty("state", "done")
        else:
            badge.setProperty("state", "pending")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(72, 72)

        title = QLabel(title_text)
        title.setObjectName("kioskProgressStageTitle")
        if active:
            title.setProperty("state", "active")
        elif completed:
            title.setProperty("state", "done")
        else:
            title.setProperty("state", "pending")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)

        layout.addWidget(badge)
        layout.addWidget(title)


class KioskRobotGuidanceProgressPage(QWidget):
    def __init__(self, *, go_home_page=None, go_call_staff_page=None):
        super().__init__()
        self.go_home_page = go_home_page
        self.go_call_staff_page = go_call_staff_page
        self.service = VisitGuideRemoteService()
        self.selected_patient = None
        self.current_session = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("kioskProgressTopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(56, 24, 56, 24)
        top_layout.setSpacing(16)

        brand = QLabel("ROPI 안내 로봇")
        brand.setObjectName("kioskProgressBrand")

        self.help_button = QPushButton("도움")
        self.help_button.setObjectName("kioskRoundIconButton")
        self.help_button.setMinimumSize(72, 72)

        self.info_button = QPushButton("안내")
        self.info_button.setObjectName("kioskRoundIconButton")
        self.info_button.setMinimumSize(72, 72)

        top_layout.addWidget(brand)
        top_layout.addStretch()
        top_layout.addWidget(self.help_button)
        top_layout.addWidget(self.info_button)

        content = QVBoxLayout()
        content.setContentsMargins(56, 44, 56, 0)
        content.setSpacing(28)

        header_wrap = QVBoxLayout()
        header_wrap.setSpacing(10)
        header_wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("로봇을 따라 이동해 주세요")
        title.setObjectName("kioskProgressTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("목적지까지 안전하게 안내해 드립니다.")
        subtitle.setObjectName("kioskProgressSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_wrap.addWidget(title)
        header_wrap.addWidget(subtitle)

        progress_card = QFrame()
        progress_card.setObjectName("kioskProgressCard")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(28, 28, 28, 28)
        progress_layout.setSpacing(18)

        line_wrap = QFrame()
        line_wrap.setObjectName("kioskProgressLineWrap")
        line_layout = QHBoxLayout(line_wrap)
        line_layout.setContentsMargins(0, 0, 0, 0)
        line_layout.setSpacing(8)

        stages = [
            KioskProgressStage(title_text="요청 접수", completed=True),
            KioskProgressStage(title_text="로봇 배정", completed=True),
            KioskProgressStage(title_text="출발 준비", completed=True),
            KioskProgressStage(title_text="이동 중", active=True),
            KioskProgressStage(title_text="도착", completed=False),
        ]
        for stage in stages:
            line_layout.addWidget(stage, 1)

        progress_layout.addWidget(line_wrap)

        robot_card = QFrame()
        robot_card.setObjectName("kioskRobotInfoCard")
        robot_layout = QHBoxLayout(robot_card)
        robot_layout.setContentsMargins(28, 28, 28, 28)
        robot_layout.setSpacing(22)

        robot_icon = QLabel("R")
        robot_icon.setObjectName("kioskRobotInfoIcon")
        robot_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        robot_icon.setFixedSize(124, 124)

        robot_text_wrap = QVBoxLayout()
        robot_text_wrap.setSpacing(14)

        top_text_row = QHBoxLayout()
        top_text_row.setSpacing(14)

        self.robot_name_label = QLabel("ROPI-01")
        self.robot_name_label.setObjectName("kioskRobotInfoTitle")

        self.robot_state_chip = QLabel("이동 중")
        self.robot_state_chip.setObjectName("kioskRobotStateChip")

        top_text_row.addWidget(self.robot_name_label)
        top_text_row.addWidget(self.robot_state_chip)
        top_text_row.addStretch()

        self.progress_bar_track = QFrame()
        self.progress_bar_track.setObjectName("kioskRobotProgressTrack")
        progress_bar_layout = QVBoxLayout(self.progress_bar_track)
        progress_bar_layout.setContentsMargins(0, 0, 0, 0)
        progress_bar_layout.setSpacing(0)

        self.progress_bar_fill = QFrame()
        self.progress_bar_fill.setObjectName("kioskRobotProgressFill")
        self.progress_bar_fill.setFixedWidth(420)
        self.progress_bar_fill.setMinimumHeight(14)
        self.progress_bar_fill.setMaximumHeight(14)

        progress_bar_layout.addWidget(self.progress_bar_fill)

        self.distance_label = QLabel("남은 거리: 약 25m")
        self.distance_label.setObjectName("kioskRobotDistanceText")

        robot_text_wrap.addLayout(top_text_row)
        robot_text_wrap.addWidget(self.progress_bar_track)
        robot_text_wrap.addWidget(self.distance_label)

        robot_layout.addWidget(robot_icon)
        robot_layout.addLayout(robot_text_wrap, 1)

        safety_notice = QFrame()
        safety_notice.setObjectName("kioskSafetyNotice")
        safety_layout = QHBoxLayout(safety_notice)
        safety_layout.setContentsMargins(24, 24, 24, 24)
        safety_layout.setSpacing(18)

        safety_icon = QLabel("↔")
        safety_icon.setObjectName("kioskSafetyNoticeIcon")
        safety_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        safety_icon.setFixedWidth(50)

        safety_text = QLabel("로봇과 적정한 거리를 유지하며 따라와 주세요.")
        safety_text.setObjectName("kioskSafetyNoticeText")
        safety_text.setWordWrap(True)

        safety_layout.addWidget(safety_icon)
        safety_layout.addWidget(safety_text, 1)

        self.request_id_label = QLabel("요청번호: -")
        self.request_id_label.setObjectName("kioskProgressRequestId")
        self.request_id_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        content.addLayout(header_wrap)
        content.addWidget(progress_card)
        content.addWidget(robot_card)
        content.addWidget(safety_notice)
        content.addWidget(self.request_id_label)
        content.addStretch()

        bottom_bar = QFrame()
        bottom_bar.setObjectName("kioskConfirmationBottomBar")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(56, 20, 56, 20)
        bottom_layout.setSpacing(24)

        self.call_staff_button = QPushButton("직원 호출")
        self.call_staff_button.setObjectName("kioskProgressPrimaryButton")
        self.call_staff_button.setMinimumHeight(72)

        self.cancel_button = QPushButton("안내 취소")
        self.cancel_button.setObjectName("kioskProgressSecondaryButton")
        self.cancel_button.setMinimumHeight(72)
        self.cancel_button.clicked.connect(self.finish_guidance)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.call_staff_button, 1)
        bottom_layout.addWidget(self.cancel_button, 1)
        bottom_layout.addStretch()

        root.addWidget(top_bar)
        root.addLayout(content, 1)
        root.addWidget(bottom_bar)

    def set_patient(self, patient, session=None):
        self.selected_patient = patient or None
        self.current_session = session or None
        if self.selected_patient:
            name = str(self.selected_patient.get("name", "-")).strip() or "-"
            room = str(self.selected_patient.get("room", "-")).strip() or "-"
            task_id = str((self.current_session or {}).get("task_id", "-")).strip() or "-"
            self.request_id_label.setText(
                f"안내 대상: {name} 어르신 / 목적지: {room} / task_id: {task_id}"
            )
        else:
            self.request_id_label.setText("안내 대상: -")

        self.refresh_runtime_status()

    def refresh_runtime_status(self):
        try:
            ok, message, status = self.service.get_guide_runtime_status()
        except Exception:
            return

        guide_runtime = (status or {}).get("guide_runtime") or {}
        last_update = guide_runtime.get("last_update") or {}
        tracking_status = str(last_update.get("tracking_status") or "").strip()
        tracking_seq = last_update.get("tracking_result_seq")

        if ok and tracking_status:
            self.robot_state_chip.setText(tracking_status)
            if tracking_status == "TRACKING":
                self.distance_label.setText("안내 추적이 정상적으로 진행 중입니다.")
            else:
                self.distance_label.setText(f"현재 상태: {tracking_status}")

        if tracking_seq is not None and self.selected_patient:
            self.request_id_label.setText(
                f"안내 대상: {self.selected_patient.get('name', '-')} / 추적 순번: {tracking_seq}"
            )

    def finish_guidance(self):
        task_id = str((self.current_session or {}).get("task_id", "")).strip()
        if not task_id:
            self.distance_label.setText("안내 종료에 필요한 task_id가 없습니다.")
            return

        pinky_id = str((self.current_session or {}).get("pinky_id", "pinky1")).strip() or "pinky1"
        try:
            success, message, _response = self.service.finish_guide_session(
                task_id=task_id,
                pinky_id=pinky_id,
                finish_reason="USER_CANCELLED",
            )
        except Exception as exc:
            self.distance_label.setText(f"안내 종료 중 오류가 발생했습니다: {exc}")
            return

        if success:
            self.distance_label.setText("안내 종료 요청이 접수되었습니다.")
            self._go_home()
            return

        self.distance_label.setText(f"안내 종료 실패: {message}")

    def _go_home(self):
        if self.go_home_page:
            self.go_home_page()


class KioskHomePage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("kioskHomePage")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("kioskTopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(56, 28, 56, 28)
        top_layout.setSpacing(18)

        brand_wrap = QVBoxLayout()
        brand_wrap.setSpacing(4)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.setContentsMargins(0, 0, 0, 0)

        brand_icon = QLabel("✚")
        brand_icon.setObjectName("kioskBrandIcon")

        brand_title = QLabel("ROPI 요양보호 서비스")
        brand_title.setObjectName("kioskBrandTitle")

        brand_row.addWidget(brand_icon)
        brand_row.addWidget(brand_title)
        brand_row.addStretch()

        brand_subtitle = QLabel("방문 등록, 어르신 찾기, 직원 호출을 한 화면에서 빠르게 진행할 수 있습니다.")
        brand_subtitle.setObjectName("kioskBrandSubtitle")
        brand_subtitle.setWordWrap(True)

        brand_wrap.addLayout(brand_row)
        brand_wrap.addWidget(brand_subtitle)

        action_wrap = QHBoxLayout()
        action_wrap.setSpacing(12)

        self.help_button = QPushButton("도움말")
        self.help_button.setObjectName("kioskSecondaryButton")
        self.help_button.setMinimumHeight(60)

        action_wrap.addWidget(self.help_button)

        top_layout.addLayout(brand_wrap, 1)
        top_layout.addLayout(action_wrap)

        content = QVBoxLayout()
        content.setContentsMargins(56, 32, 56, 0)
        content.setSpacing(28)

        hero_wrap = QVBoxLayout()
        hero_wrap.setSpacing(10)

        hero_eyebrow = QLabel("방문자 키오스크")
        hero_eyebrow.setObjectName("kioskEyebrow")

        hero_title = QLabel("무엇을 도와드릴까요?")
        hero_title.setObjectName("kioskHeroTitle")

        hero_desc = QLabel("필요한 서비스를 선택하면 다음 단계로 바로 이동합니다.")
        hero_desc.setObjectName("kioskHeroDesc")

        hero_wrap.addWidget(hero_eyebrow, alignment=Qt.AlignmentFlag.AlignHCenter)
        hero_wrap.addWidget(hero_title, alignment=Qt.AlignmentFlag.AlignHCenter)
        hero_wrap.addWidget(hero_desc, alignment=Qt.AlignmentFlag.AlignHCenter)

        card_grid = QGridLayout()
        card_grid.setHorizontalSpacing(22)
        card_grid.setVerticalSpacing(22)

        self.search_card = KioskHomeActionCard(
            accent="blue",
            icon_text="⌕",
            title_text="어르신 찾기",
            desc_text="찾으시는 어르신의 병실과 위치 안내를 확인합니다.",
        )
        self.register_card = KioskHomeActionCard(
            accent="green",
            icon_text="✓",
            title_text="방문 등록",
            desc_text="방문 목적과 인적 사항을 입력해 접수 절차를 시작합니다.",
        )
        self.call_card = KioskHomeActionCard(
            accent="coral",
            icon_text="!",
            title_text="직원 호출",
            desc_text="직접 도움이 필요할 때 직원에게 바로 요청을 보냅니다.",
        )

        card_grid.addWidget(self.search_card, 0, 0)
        card_grid.addWidget(self.register_card, 0, 1)
        card_grid.addWidget(self.call_card, 0, 2)

        footer = QFrame()
        footer.setObjectName("kioskFooterBar")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 18, 24, 18)
        footer_layout.setSpacing(18)

        footer_layout.addWidget(
            KioskFooterStat(
                icon_text="◎",
                title_text="현재 위치",
                value_text="1층 로비 안내 데스크",
            )
        )
        footer_layout.addWidget(
            KioskFooterStat(
                icon_text="◴",
                title_text="방문 가능 시간",
                value_text="오전 9시 - 오후 8시",
            )
        )
        footer_layout.addWidget(
            KioskFooterStat(
                icon_text="R",
                title_text="안내 로봇 상태",
                value_text="준비 완료",
            )
        )

        content.addLayout(hero_wrap)
        content.addLayout(card_grid)
        content.addStretch()

        root.addWidget(top_bar)
        root.addLayout(content, 1)
        root.addWidget(footer)


class KioskHomeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ROPI Kiosk")
        self.resize(1440, 960)
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("kioskRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.home_page = KioskHomePage()
        self.search_page = KioskResidentSearchPage(
            go_home_page=lambda: self.stack.setCurrentWidget(self.home_page),
            go_confirmation_page=self._show_confirmation_page,
            go_back_page=lambda: self.stack.setCurrentWidget(self.home_page),
        )
        self.confirmation_page = KioskGuideConfirmationPage(
            go_home_page=lambda: self.stack.setCurrentWidget(self.home_page),
            go_back_page=lambda: self.stack.setCurrentWidget(self.search_page),
            go_progress_page=self._show_progress_page,
        )
        self.progress_page = KioskRobotGuidanceProgressPage(
            go_home_page=lambda: self.stack.setCurrentWidget(self.home_page),
        )

        self.home_page.search_card.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.search_page)
        )

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.search_page)
        self.stack.addWidget(self.confirmation_page)
        self.stack.addWidget(self.progress_page)
        root_layout.addWidget(self.stack)
        self.setCentralWidget(root)

    def _show_confirmation_page(self, patient):
        self.confirmation_page.set_patient(patient)
        self.stack.setCurrentWidget(self.confirmation_page)

    def _show_progress_page(self, patient, session=None):
        self.progress_page.set_patient(patient, session=session)
        self.stack.setCurrentWidget(self.progress_page)


__all__ = ["KioskHomeWindow", "load_stylesheet"]


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())

    window = KioskHomeWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
