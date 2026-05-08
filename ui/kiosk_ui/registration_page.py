from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.kiosk_ui.shared_widgets import KioskResidentPersonIcon
from ui.utils.network.service_clients import KioskVisitorRemoteService


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
        self.resident_summary_card.setMinimumHeight(176)
        summary_layout = QHBoxLayout(self.resident_summary_card)
        summary_layout.setContentsMargins(22, 18, 22, 18)
        summary_layout.setSpacing(18)

        avatar = QFrame()
        avatar.setObjectName("kioskResidentAvatar")
        avatar.setFixedSize(84, 84)
        avatar_layout = QVBoxLayout(avatar)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_layout.addWidget(KioskResidentPersonIcon())

        resident_text = QVBoxLayout()
        resident_text.setSpacing(4)

        self.resident_name_label = QLabel("선택된 어르신이 없습니다")
        self.resident_name_label.setObjectName("kioskResidentName")
        self.resident_name_label.setMinimumHeight(48)
        self.resident_name_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self.resident_birth_label = QLabel("생년월일 -")
        self.resident_birth_label.setObjectName("kioskResidentMeta")
        self.resident_birth_label.setMinimumHeight(24)
        self.resident_birth_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self.resident_room_label = QLabel("호실 -")
        self.resident_room_label.setObjectName("kioskResidentRoom")
        self.resident_room_label.setMinimumHeight(28)
        self.resident_room_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self.resident_visit_label = QLabel("방문 상태 -")
        self.resident_visit_label.setObjectName("kioskResidentMeta")
        self.resident_visit_label.setMinimumHeight(24)
        self.resident_visit_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        resident_text.addWidget(self.resident_name_label)
        resident_text.addWidget(self.resident_birth_label)
        resident_text.addWidget(self.resident_room_label)
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

    @classmethod
    def _resident_from_lookup_match(cls, match):
        return {
            "member_id": int(match["member_id"]),
            "display_name": str(match.get("display_name") or "-").strip() or "-",
            "birth_date": str(match.get("birth_date") or "-").strip() or "-",
            "room_no": cls._normalize_room(match.get("room_no")),
            "visit_available": bool(match.get("visit_available", True)),
            "guide_available": bool(match.get("guide_available", True)),
        }

    def _show_resident_result(self, resident):
        self.resident_name_label.setText(f"{resident['display_name']} 어르신")
        self.resident_birth_label.setText(f"생년월일 {resident['birth_date']}")
        self.resident_room_label.setText(self._format_room_label(resident.get("room_no")))
        self.resident_visit_label.setText(
            "방문 등록 가능" if resident.get("visit_available") else "방문 제한"
        )

    def _clear_resident_result(self):
        self.resident_name_label.setText("선택된 어르신이 없습니다")
        self.resident_birth_label.setText("생년월일 -")
        self.resident_room_label.setText("호실 -")
        self.resident_visit_label.setText("방문 상태 -")

    def _on_visitor_context_changed(self):
        if self.selected_resident:
            self.selected_resident = None
            self._clear_resident_result()
            self._set_status("방문자 정보가 변경되어 어르신 검색을 다시 확인해 주세요.")
        self._sync_action_state()

    def _set_status(self, text, *, visible=True):
        if not visible or not text:
            return

        if "방문자 정보와 개인정보" in text:
            self._show_resident_message(
                "방문자 정보 입력 필요",
                "방문자 정보와 개인정보 동의를 먼저 완료해 주세요.",
            )
            return
        if "만나실 어르신" in text:
            self._show_resident_message("어르신 검색 필요", text)
            return
        if "일치하는" in text:
            self._show_resident_message(
                "검색 결과가 없습니다",
                "이름 또는 호실을 다시 확인해 주세요.",
            )
            return
        if "오류" in text or "실패" in text:
            self._show_resident_message("처리 실패", text)
            return

        self._show_resident_message("안내", text)

    def _show_resident_message(self, title, detail):
        self.resident_name_label.setText(title)
        self.resident_birth_label.setText(detail)
        self.resident_room_label.setText("호실 -")
        self.resident_visit_label.setText("방문 상태 -")

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

    @classmethod
    def _format_room_label(cls, room_no):
        room = cls._normalize_room(room_no)
        if room == "-":
            return "호실 -"
        return f"호실 {room}호"

    def _go_home(self):
        if self.go_home_page:
            self.go_home_page()

    def _go_back(self):
        if self.go_back_page:
            self.go_back_page()
            return
        self._go_home()


__all__ = ["KioskPurposeOptionCard", "KioskVisitorRegistrationPage"]
