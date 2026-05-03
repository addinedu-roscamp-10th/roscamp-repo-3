import sys
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
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
from ui.utils.network.service_clients import KioskVisitorRemoteService, VisitGuideRemoteService


class KioskActionIconGlyph(QWidget):
    def __init__(self, *, icon_name, accent):
        super().__init__()
        self.icon_name = icon_name
        self.accent = accent
        self.setObjectName("kioskActionIconGlyph")
        self.setFixedSize(84, 84)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(
            {
                "blue": "#00477F",
                "green": "#2F855A",
                "coral": "#A23C22",
            }.get(self.accent, "#1E293B")
        )
        pen = QPen(color, 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.icon_name == "resident_search":
            self._draw_resident_search(painter)
        elif self.icon_name == "visitor_registration":
            self._draw_visitor_registration(painter)
        else:
            self._draw_staff_call(painter)

    def _draw_resident_search(self, painter):
        painter.drawEllipse(QRectF(20, 15, 40, 40))
        painter.drawLine(53, 50, 73, 70)

    def _draw_visitor_registration(self, painter):
        painter.drawRoundedRect(QRectF(18, 10, 48, 64), 8, 8)
        painter.drawLine(30, 27, 54, 27)
        painter.drawLine(30, 40, 50, 40)
        painter.drawLine(30, 53, 43, 53)
        painter.drawLine(30, 61, 39, 70)
        painter.drawLine(39, 70, 60, 47)

    def _draw_staff_call(self, painter):
        bell = QPainterPath()
        bell.moveTo(22, 57)
        bell.cubicTo(27, 50, 27, 43, 27, 36)
        bell.cubicTo(27, 24, 33, 18, 42, 18)
        bell.cubicTo(51, 18, 57, 24, 57, 36)
        bell.cubicTo(57, 43, 57, 50, 62, 57)
        bell.lineTo(22, 57)
        painter.drawPath(bell)
        painter.drawArc(QRectF(34, 58, 16, 14), 200 * 16, 140 * 16)
        painter.drawLine(15, 26, 8, 18)
        painter.drawLine(69, 26, 76, 18)


class KioskHomeActionCard(QFrame):
    clicked = pyqtSignal()

    def __init__(self, *, accent, icon_name, title_text, desc_text):
        super().__init__()
        self.setObjectName("kioskActionCard")
        self.setProperty("accent", accent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        body = QFrame()
        body.setObjectName("kioskActionCardBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(48, 44, 48, 44)
        body_layout.setSpacing(24)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("kioskIconBubble")
        icon_wrap.setProperty("accent", accent)
        icon_wrap.setFixedSize(128, 128)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon = KioskActionIconGlyph(icon_name=icon_name, accent=accent)
        icon_layout.addWidget(self.icon)

        self.title = QLabel(title_text)
        self.title.setObjectName("kioskActionTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.desc = QLabel(desc_text)
        self.desc.setObjectName("kioskActionDesc")
        self.desc.setWordWrap(True)
        self.desc.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body_layout.addStretch()
        body_layout.addWidget(icon_wrap, alignment=Qt.AlignmentFlag.AlignHCenter)
        body_layout.addWidget(self.title)
        body_layout.addWidget(self.desc)
        body_layout.addStretch()

        layout.addWidget(body, 1)

        for widget in [icon_wrap, self.icon, self.title, self.desc]:
            widget.mousePressEvent = self._child_click

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _child_click(self, event):
        self.clicked.emit()


class KioskSearchIconButton(QPushButton):
    def __init__(self):
        super().__init__("")
        self.setProperty("iconName", "search")

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#FFFFFF"), 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        cx = self.width() / 2 - 8
        cy = self.height() / 2 - 5
        painter.drawEllipse(QRectF(cx - 15, cy - 15, 30, 30))
        painter.drawLine(int(cx + 11), int(cy + 11), int(cx + 28), int(cy + 28))


class KioskResidentPersonIcon(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("kioskResidentPersonIcon")
        self.setFixedSize(56, 56)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen(QColor("#2F855A"), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawEllipse(QRectF(22, 10, 12, 12))

        shoulders = QPainterPath()
        shoulders.moveTo(14, 42)
        shoulders.cubicTo(14, 32, 21, 27, 28, 27)
        shoulders.cubicTo(35, 27, 42, 32, 42, 42)
        shoulders.lineTo(14, 42)
        painter.drawPath(shoulders)


class KioskNavigationActionButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self.setProperty("iconName", "navigation")

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#FFFFFF")))

        center_y = self.height() / 2
        path = QPainterPath()
        path.moveTo(36, center_y - 15)
        path.lineTo(56, center_y)
        path.lineTo(36, center_y + 15)
        path.lineTo(42, center_y)
        path.closeSubpath()
        painter.drawPath(path)


class KioskFooterNavigationButton(QPushButton):
    def __init__(self, text, icon_name):
        super().__init__(text)
        self.icon_name = icon_name
        self.setProperty("iconName", icon_name)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#111C2D"), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        text_width = self.fontMetrics().horizontalAdvance(self.text())
        icon_center_x = int(self.width() / 2 - text_width / 2 - 34)
        icon_center_y = int(self.height() / 2)

        if self.icon_name == "arrow_back":
            self._draw_back_icon(painter, icon_center_x, icon_center_y)
        else:
            self._draw_home_icon(painter, icon_center_x, icon_center_y)

    def _draw_back_icon(self, painter, x, y):
        painter.drawLine(x + 14, y, x - 14, y)
        painter.drawLine(x - 14, y, x - 3, y - 11)
        painter.drawLine(x - 14, y, x - 3, y + 11)

    def _draw_home_icon(self, painter, x, y):
        painter.drawLine(x - 15, y - 3, x, y - 17)
        painter.drawLine(x, y - 17, x + 15, y - 3)
        painter.drawRoundedRect(QRectF(x - 11, y - 3, 22, 20), 3, 3)
        painter.drawLine(x - 3, y + 17, x - 3, y + 6)
        painter.drawLine(x + 3, y + 6, x + 3, y + 17)


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


class KioskPurposeIcon(QWidget):
    def __init__(self, *, icon_name):
        super().__init__()
        self.icon_name = icon_name
        self.setObjectName("kioskPurposeIcon")
        self.setFixedSize(42, 42)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#00477F"), 4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.icon_name == "family":
            painter.drawEllipse(QRectF(8, 6, 12, 12))
            painter.drawEllipse(QRectF(23, 6, 12, 12))
            painter.drawArc(QRectF(4, 20, 18, 18), 15 * 16, 150 * 16)
            painter.drawArc(QRectF(21, 20, 18, 18), 15 * 16, 150 * 16)
        elif self.icon_name == "friend":
            painter.drawEllipse(QRectF(14, 5, 14, 14))
            painter.drawEllipse(QRectF(4, 17, 11, 11))
            painter.drawEllipse(QRectF(27, 17, 11, 11))
            painter.drawArc(QRectF(9, 22, 24, 18), 20 * 16, 140 * 16)
        elif self.icon_name == "consult":
            painter.drawRoundedRect(QRectF(6, 8, 30, 24), 5, 5)
            painter.drawLine(13, 17, 29, 17)
            painter.drawLine(13, 24, 23, 24)
            painter.drawLine(18, 32, 12, 38)
        else:
            painter.setBrush(QBrush(QColor("#00477F")))
            painter.drawEllipse(QRectF(8, 18, 6, 6))
            painter.drawEllipse(QRectF(18, 18, 6, 6))
            painter.drawEllipse(QRectF(28, 18, 6, 6))


class KioskPurposeOptionCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, *, key, label, icon_name):
        super().__init__()
        self.key = key
        self.setObjectName("kioskPurposeOptionCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_bubble = QFrame()
        icon_bubble.setObjectName("kioskPurposeIconBubble")
        icon_bubble.setFixedSize(52, 52)
        icon_layout = QVBoxLayout(icon_bubble)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(KioskPurposeIcon(icon_name=icon_name))

        self.label = QLabel(label)
        self.label.setObjectName("kioskPurposeLabel")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon_bubble, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.label)

        for widget in [icon_bubble, self.label]:
            widget.mousePressEvent = self._child_click

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(event)

    def _child_click(self, event):
        self.clicked.emit(self.key)


class KioskVisitorRegistrationPage(QWidget):
    PURPOSE_OPTIONS = (
        {"key": "family", "label": "가족 면회", "icon": "family"},
        {"key": "friend", "label": "지인 방문", "icon": "friend"},
        {"key": "consult", "label": "상담/문의", "icon": "consult"},
        {"key": "other", "label": "기타", "icon": "other"},
    )

    def __init__(
        self,
        *,
        go_home_page=None,
        go_confirmation_page=None,
        go_back_page=None,
        service=None,
    ):
        super().__init__()
        self.setObjectName("kioskVisitorRegistrationPage")
        self.go_home_page = go_home_page
        self.go_confirmation_page = go_confirmation_page
        self.go_back_page = go_back_page
        self.service = service or KioskVisitorRemoteService()
        self.selected_resident = None
        self.selected_visit_purpose = None
        self.visitor_session = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("kioskRegistrationTopBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(56, 28, 56, 28)
        header_layout.setSpacing(18)

        brand_wrap = QHBoxLayout()
        brand_wrap.setSpacing(14)
        brand_wrap.setContentsMargins(0, 0, 0, 0)

        brand_icon = QLabel("✚")
        brand_icon.setObjectName("kioskBrandIcon")

        brand = QLabel("ROPI 요양보호 서비스")
        brand.setObjectName("kioskRegistrationBrand")

        brand_wrap.addWidget(brand_icon)
        brand_wrap.addWidget(brand)
        header_layout.addLayout(brand_wrap)
        header_layout.addStretch()

        self.call_staff_button = QPushButton("직원 호출")
        self.call_staff_button.setObjectName("kioskSearchCallButton")
        self.call_staff_button.setMinimumHeight(72)
        header_layout.addWidget(self.call_staff_button)

        canvas = QFrame()
        canvas.setObjectName("kioskRegistrationCanvas")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        page_shell = QVBoxLayout()
        page_shell.setContentsMargins(56, 30, 56, 0)
        page_shell.setSpacing(22)
        page_shell.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("방문자 등록")
        title.setObjectName("kioskSearchPageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("방문자 정보를 입력한 뒤 만나실 어르신을 확인해 주세요.")
        subtitle.setObjectName("kioskSearchPageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        content_row = QHBoxLayout()
        content_row.setSpacing(24)

        form_card = QFrame()
        form_card.setObjectName("kioskRegistrationFormCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(28, 26, 28, 26)
        form_layout.setSpacing(16)

        form_title = QLabel("방문자 정보")
        form_title.setObjectName("kioskRegistrationSectionTitle")

        name_field, self.visitor_name_input = self._create_labeled_input(
            "성함",
            "예: 김민수",
        )
        phone_field, self.phone_input = self._create_labeled_input(
            "연락처",
            "예: 010-1234-5678",
        )
        relation_field, self.relationship_input = self._create_labeled_input(
            "관계",
            "예: 아들, 보호자",
        )

        self.privacy_checkbox = QCheckBox("개인정보 수집 및 방문 기록 저장에 동의합니다.")
        self.privacy_checkbox.setObjectName("kioskPrivacyCheckbox")
        self.privacy_checkbox.stateChanged.connect(self._sync_action_state)

        form_layout.addWidget(form_title)
        form_layout.addWidget(name_field)
        form_layout.addWidget(phone_field)
        form_layout.addWidget(relation_field)
        form_layout.addWidget(self.privacy_checkbox)
        form_layout.addStretch()

        resident_card = QFrame()
        resident_card.setObjectName("kioskRegistrationResidentCard")
        resident_layout = QVBoxLayout(resident_card)
        resident_layout.setContentsMargins(28, 26, 28, 26)
        resident_layout.setSpacing(16)

        resident_title = QLabel("만나실 어르신")
        resident_title.setObjectName("kioskRegistrationSectionTitle")

        purpose_title = QLabel("방문 목적")
        purpose_title.setObjectName("kioskRegistrationSectionTitle")

        purpose_row = QHBoxLayout()
        purpose_row.setSpacing(10)
        self.purpose_cards = {}
        for option in self.PURPOSE_OPTIONS:
            card = KioskPurposeOptionCard(
                key=option["key"],
                label=option["label"],
                icon_name=option["icon"],
            )
            card.clicked.connect(self.select_visit_purpose)
            self.purpose_cards[option["key"]] = card
            purpose_row.addWidget(card, 1)

        resident_hint = QLabel("방문자 정보를 먼저 입력하면 어르신 검색을 사용할 수 있습니다.")
        resident_hint.setObjectName("kioskRegistrationHint")
        resident_hint.setWordWrap(True)

        search_card = QFrame()
        search_card.setObjectName("kioskSearchInputCard")
        search_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        search_card.setFixedHeight(92)
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        self.resident_search_input = QLineEdit()
        self.resident_search_input.setObjectName("kioskSearchInput")
        self.resident_search_input.setPlaceholderText("성함 또는 방 번호 입력")
        self.resident_search_input.setFixedHeight(72)
        self.resident_search_input.textChanged.connect(self._sync_action_state)
        self.resident_search_input.returnPressed.connect(self.search_resident)

        self.search_button = KioskSearchIconButton()
        self.search_button.setObjectName("kioskSearchSubmitButton")
        self.search_button.setMinimumSize(128, 88)
        self.search_button.clicked.connect(self.search_resident)

        search_layout.addWidget(self.resident_search_input, 1)
        search_layout.addWidget(self.search_button)

        self.resident_summary_card = QFrame()
        self.resident_summary_card.setObjectName("kioskRegistrationResidentSummary")
        summary_layout = QHBoxLayout(self.resident_summary_card)
        summary_layout.setContentsMargins(22, 22, 22, 22)
        summary_layout.setSpacing(18)

        avatar = QFrame()
        avatar.setObjectName("kioskResidentAvatar")
        avatar.setFixedSize(84, 84)
        avatar_layout = QVBoxLayout(avatar)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_layout.addWidget(KioskResidentPersonIcon())

        resident_text = QVBoxLayout()
        resident_text.setSpacing(8)

        self.resident_name_label = QLabel("선택된 어르신이 없습니다")
        self.resident_name_label.setObjectName("kioskResidentName")

        self.resident_birth_label = QLabel("생년월일 -")
        self.resident_birth_label.setObjectName("kioskResidentMeta")

        self.resident_visit_label = QLabel("방문 상태 -")
        self.resident_visit_label.setObjectName("kioskResidentMeta")

        resident_text.addWidget(self.resident_name_label)
        resident_text.addWidget(self.resident_birth_label)
        resident_text.addWidget(self.resident_visit_label)

        summary_layout.addWidget(avatar)
        summary_layout.addLayout(resident_text, 1)

        resident_layout.addWidget(purpose_title)
        resident_layout.addLayout(purpose_row)
        resident_layout.addWidget(resident_title)
        resident_layout.addWidget(resident_hint)
        resident_layout.addWidget(search_card)
        resident_layout.addWidget(self.resident_summary_card)
        resident_layout.addStretch()

        content_row.addWidget(form_card, 1)
        content_row.addWidget(resident_card, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("kioskSearchStatusText")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setVisible(False)

        page_shell.addWidget(title)
        page_shell.addWidget(subtitle)
        page_shell.addLayout(content_row, 1)
        canvas_layout.addLayout(page_shell, 1)

        bottom_bar = QFrame()
        bottom_bar.setObjectName("kioskSearchBottomBar")
        action_row = QHBoxLayout(bottom_bar)
        action_row.setContentsMargins(56, 20, 56, 20)
        action_row.setSpacing(24)

        self.back_button = KioskFooterNavigationButton("이전", "arrow_back")
        self.back_button.setObjectName("kioskSearchFooterButton")
        self.back_button.setMinimumHeight(72)
        self.back_button.clicked.connect(self._go_back)

        self.home_button = KioskFooterNavigationButton("처음으로", "home")
        self.home_button.setObjectName("kioskSearchFooterButton")
        self.home_button.setMinimumHeight(72)
        self.home_button.clicked.connect(self._go_home)

        self.register_button = QPushButton("등록하기")
        self.register_button.setObjectName("kioskRegistrationPrimaryButton")
        self.register_button.setMinimumHeight(72)
        self.register_button.clicked.connect(self.register_visit)

        action_row.addWidget(self.back_button)
        action_row.addStretch()
        action_row.addWidget(self.home_button)
        action_row.addWidget(self.register_button)

        root.addWidget(header)
        root.addWidget(canvas, 1)
        root.addWidget(bottom_bar)

        for input_widget in [
            self.visitor_name_input,
            self.phone_input,
            self.relationship_input,
        ]:
            input_widget.textChanged.connect(self._on_visitor_context_changed)

        self._sync_action_state()

    def _create_labeled_input(self, label_text, placeholder_text):
        field = QFrame()
        field.setObjectName("kioskRegistrationField")
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("kioskRegistrationFieldLabel")

        input_widget = QLineEdit()
        input_widget.setObjectName("kioskRegistrationInput")
        input_widget.setPlaceholderText(placeholder_text)
        input_widget.setFixedHeight(72)

        layout.addWidget(label)
        layout.addWidget(input_widget)
        return field, input_widget

    def search_resident(self):
        if not self._visitor_context_ready():
            self._set_status("방문자 정보와 개인정보 동의를 먼저 완료해 주세요.")
            self._sync_action_state()
            return

        keyword = self.resident_search_input.text().strip()
        if not keyword:
            self._set_status("만나실 어르신의 성함 또는 방 번호를 입력해 주세요.")
            self._sync_action_state()
            return

        try:
            response = self.service.lookup_residents(keyword=keyword, limit=5)
        except Exception as exc:
            self.selected_resident = None
            self._clear_resident_result()
            self._set_status(f"검색 중 오류가 발생했습니다: {exc}")
            self._sync_action_state()
            return

        result_code = response.get("result_code")
        matches = response.get("matches") or []
        if result_code != "FOUND" or not matches:
            self.selected_resident = None
            self._clear_resident_result()
            self._set_status(
                response.get("result_message") or "일치하는 어르신 정보가 없습니다."
            )
            self._sync_action_state()
            return

        self.selected_resident = self._resident_from_lookup_match(matches[0])
        self._show_resident_result(self.selected_resident)
        self._set_status("", visible=False)
        self._sync_action_state()

    def register_visit(self):
        if not self._visitor_context_ready():
            self._set_status("방문자 정보와 개인정보 동의를 먼저 완료해 주세요.")
            self._sync_action_state()
            return
        if not self.selected_resident:
            self._set_status("만나실 어르신을 먼저 검색해 주세요.")
            self._sync_action_state()
            return

        payload = self._registration_payload()
        try:
            response = self.service.register_visit(**payload)
        except Exception as exc:
            self._set_status(f"방문 등록 중 오류가 발생했습니다: {exc}")
            return

        if response.get("result_code") != "REGISTERED":
            self.visitor_session = None
            self._set_status(
                response.get("result_message") or "방문 등록을 완료하지 못했습니다."
            )
            return

        self.visitor_session = {
            "visitor_id": int(response["visitor_id"]),
            "member_id": int(response["member_id"]),
            "resident_name": (
                response.get("resident_name") or self.selected_resident["display_name"]
            ),
            "room_no": response.get("room_no") or "-",
            "visit_status": response.get("visit_status") or "면회 가능",
        }
        patient = self._patient_from_registration_response(response)
        self._set_status("방문 등록이 완료되었습니다. 안내 확인 화면으로 이동합니다.")

        if self.go_confirmation_page:
            self.go_confirmation_page(patient)

    def reset_form(self):
        for input_widget in [
            self.visitor_name_input,
            self.phone_input,
            self.relationship_input,
            self.resident_search_input,
        ]:
            input_widget.clear()
        self.privacy_checkbox.setChecked(False)
        self.selected_visit_purpose = None
        self.selected_resident = None
        self.visitor_session = None
        self._clear_resident_result()
        self._set_status("", visible=False)
        self._sync_action_state()
        self._refresh_purpose_card_styles()

    def _registration_payload(self):
        return {
            "visitor_name": self.visitor_name_input.text().strip(),
            "phone_no": self.phone_input.text().strip(),
            "relationship": self.relationship_input.text().strip(),
            "visit_purpose": self.selected_visit_purpose,
            "target_member_id": int(self.selected_resident["member_id"]),
            "privacy_agreed": self.privacy_checkbox.isChecked(),
            "kiosk_id": None,
        }

    def _patient_from_registration_response(self, response):
        return {
            "member_id": int(response.get("member_id") or self.selected_resident["member_id"]),
            "visitor_id": int(response["visitor_id"]),
            "name": str(response.get("resident_name") or self.selected_resident["display_name"]),
            "room": self._normalize_room(response.get("room_no")),
            "visit_status": response.get("visit_status") or "면회 가능",
            "guide_available": bool(self.selected_resident.get("guide_available")),
        }

    @staticmethod
    def _resident_from_lookup_match(match):
        return {
            "member_id": int(match["member_id"]),
            "display_name": str(match.get("display_name") or "-").strip() or "-",
            "birth_date": str(match.get("birth_date") or "-").strip() or "-",
            "visit_available": bool(match.get("visit_available", True)),
            "guide_available": bool(match.get("guide_available", True)),
        }

    def _show_resident_result(self, resident):
        self.resident_name_label.setText(f"{resident['display_name']} 어르신")
        self.resident_birth_label.setText(f"생년월일 {resident['birth_date']}")
        self.resident_visit_label.setText(
            "방문 등록 가능" if resident.get("visit_available") else "방문 제한"
        )

    def _clear_resident_result(self):
        self.resident_name_label.setText("선택된 어르신이 없습니다")
        self.resident_birth_label.setText("생년월일 -")
        self.resident_visit_label.setText("방문 상태 -")

    def _on_visitor_context_changed(self):
        if self.selected_resident:
            self.selected_resident = None
            self._clear_resident_result()
            self._set_status("방문자 정보가 변경되어 어르신 검색을 다시 확인해 주세요.")
        self._sync_action_state()

    def _set_status(self, text, *, visible=True):
        self.status_label.setText(text)
        self.status_label.setVisible(bool(visible and text))

    def select_visit_purpose(self, purpose_key):
        option = next(
            (item for item in self.PURPOSE_OPTIONS if item["key"] == purpose_key),
            None,
        )
        if option is None:
            return
        previous = self.selected_visit_purpose
        self.selected_visit_purpose = option["label"]
        self._refresh_purpose_card_styles()
        if previous != self.selected_visit_purpose:
            self._on_visitor_context_changed()
            return
        self._sync_action_state()

    def _refresh_purpose_card_styles(self):
        selected_key = next(
            (
                option["key"]
                for option in self.PURPOSE_OPTIONS
                if option["label"] == self.selected_visit_purpose
            ),
            None,
        )
        for key, card in self.purpose_cards.items():
            card.setProperty("selected", key == selected_key)
            card.style().unpolish(card)
            card.style().polish(card)

    def _visitor_context_ready(self):
        return (
            bool(self.visitor_name_input.text().strip())
            and bool(self.phone_input.text().strip())
            and bool(self.relationship_input.text().strip())
            and bool(self.selected_visit_purpose)
            and self.privacy_checkbox.isChecked()
        )

    def _sync_action_state(self):
        can_search = self._visitor_context_ready() and bool(
            self.resident_search_input.text().strip()
        )
        self.search_button.setEnabled(can_search)
        can_register = bool(
            self.selected_resident
            and self.selected_resident.get("visit_available")
            and self._visitor_context_ready()
        )
        self.register_button.setEnabled(can_register)

    @staticmethod
    def _normalize_room(room_no):
        room = str(room_no or "").strip()
        if room.endswith("호"):
            room = room[:-1].strip()
        return room or "-"

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
        top_layout.setContentsMargins(64, 36, 64, 36)
        top_layout.setSpacing(24)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(18)
        brand_row.setContentsMargins(0, 0, 0, 0)

        brand_icon = QLabel("✚")
        brand_icon.setObjectName("kioskBrandIcon")
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        brand_title = QLabel("ROPI 요양보호 서비스")
        brand_title.setObjectName("kioskBrandTitle")

        brand_row.addWidget(brand_icon)
        brand_row.addWidget(brand_title)
        brand_row.addStretch()

        top_layout.addLayout(brand_row, 1)

        canvas = QFrame()
        canvas.setObjectName("kioskHomeCanvas")
        content = QVBoxLayout(canvas)
        content.setContentsMargins(64, 32, 64, 48)
        content.setSpacing(64)

        hero_wrap = QVBoxLayout()
        hero_wrap.setSpacing(0)
        hero_wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hero_title = QLabel("무엇을 도와드릴까요?")
        hero_title.setObjectName("kioskHeroTitle")
        hero_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hero_wrap.addWidget(hero_title)

        card_grid = QGridLayout()
        card_grid.setHorizontalSpacing(24)
        card_grid.setVerticalSpacing(24)

        self.register_card = KioskHomeActionCard(
            accent="green",
            icon_name="visitor_registration",
            title_text="방문 등록",
            desc_text="시설 방문을 위해 인적 사항을 등록합니다.",
        )
        self.call_card = KioskHomeActionCard(
            accent="coral",
            icon_name="staff_call",
            title_text="직원 호출",
            desc_text="도움이 필요하시면 직원을 연결해 드립니다.",
        )

        card_grid.addWidget(self.register_card, 0, 0)
        card_grid.addWidget(self.call_card, 0, 1)

        footer = QFrame()
        footer.setObjectName("kioskFooterBar")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(64, 20, 64, 20)
        footer_layout.setSpacing(24)

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

        content.addStretch()
        content.addLayout(hero_wrap)
        content.addLayout(card_grid, 1)
        content.addStretch()

        root.addWidget(top_bar)
        root.addWidget(canvas, 1)
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
        self.registration_page = KioskVisitorRegistrationPage(
            go_home_page=lambda: self.stack.setCurrentWidget(self.home_page),
            go_confirmation_page=self._show_confirmation_page,
            go_back_page=lambda: self.stack.setCurrentWidget(self.home_page),
        )
        self.confirmation_page = KioskGuideConfirmationPage(
            go_home_page=lambda: self.stack.setCurrentWidget(self.home_page),
            go_back_page=lambda: self.stack.setCurrentWidget(self.registration_page),
            go_progress_page=self._show_progress_page,
        )
        self.progress_page = KioskRobotGuidanceProgressPage(
            go_home_page=lambda: self.stack.setCurrentWidget(self.home_page),
        )

        self.home_page.register_card.clicked.connect(
            lambda: self._show_registration_page(focus_resident_search=False)
        )

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.registration_page)
        self.stack.addWidget(self.confirmation_page)
        self.stack.addWidget(self.progress_page)
        root_layout.addWidget(self.stack)
        self.setCentralWidget(root)

    def _show_registration_page(self, *, focus_resident_search=False):
        self.registration_page.reset_form()
        self.stack.setCurrentWidget(self.registration_page)
        if focus_resident_search:
            self.registration_page.resident_search_input.setFocus()
            return
        self.registration_page.visitor_name_input.setFocus()

    def _show_confirmation_page(self, patient):
        self.confirmation_page.set_patient(patient)
        self.stack.setCurrentWidget(self.confirmation_page)

    def _show_progress_page(self, patient, session=None):
        self.progress_page.set_patient(patient, session=session)
        self.stack.setCurrentWidget(self.progress_page)


__all__ = ["KioskHomeWindow", "KioskVisitorRegistrationPage", "load_stylesheet"]


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())

    window = KioskHomeWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
