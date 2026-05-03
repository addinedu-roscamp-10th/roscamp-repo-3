from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from PyQt6.QtCore import QDateTime, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


NavItem = tuple[str, str]


class SystemStatusStrip(QFrame):
    DEFAULT_STATUSES: Mapping[str, str] = {
        "관제 서버": "unknown",
        "데이터베이스": "unknown",
        "ROS2": "unknown",
        "AI 서버": "unknown",
    }

    _STATUS_TEXT = {
        "online": "정상",
        "warning": "주의",
        "error": "오류",
        "offline": "오류",
        "unknown": "확인 중",
        "disabled": "미연동",
    }

    _STATUS_OBJECT_NAME = {
        "online": "systemStatusOnline",
        "warning": "systemStatusWarning",
        "error": "systemStatusError",
        "offline": "systemStatusError",
        "unknown": "systemStatusUnknown",
        "disabled": "systemStatusWarning",
    }

    def __init__(self, statuses: Mapping[str, str] | None = None):
        super().__init__()
        self.setObjectName("systemStatusStrip")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(6)
        self.set_statuses(statuses)

    def set_statuses(self, statuses: Mapping[str, str] | None = None) -> None:
        self._clear()
        merged = dict(self.DEFAULT_STATUSES)
        if statuses:
            merged.update(statuses)

        for component, status in merged.items():
            normalized = self._normalize_status(status)
            chip = QLabel(f"{component} {self._STATUS_TEXT[normalized]}")
            chip.setObjectName(self._STATUS_OBJECT_NAME[normalized])
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(chip)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _normalize_status(self, status: str) -> str:
        normalized = (status or "unknown").lower()
        if normalized not in self._STATUS_OBJECT_NAME:
            return "unknown"
        return normalized


class PageHeader(QFrame):
    def __init__(
        self,
        title: str,
        subtitle: str = "",
        statuses: Mapping[str, str] | None = None,
        show_status: bool = False,
    ):
        super().__init__()
        self.setObjectName("pageHeader")

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(16)

        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("pageTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("pageSubtitle")

        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)

        root.addLayout(title_box, 1)

        self.status_strip = None
        if show_status or statuses is not None:
            self.status_strip = SystemStatusStrip(statuses)
            root.addWidget(self.status_strip, 0, Qt.AlignmentFlag.AlignTop)

    def set_text(self, title: str, subtitle: str = "") -> None:
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)


class PageTimeCard(QFrame):
    def __init__(
        self,
        *,
        object_name: str = "pageTimeCard",
        show_last_update: bool = True,
        status_text: str = "",
        refresh_text: str | None = None,
        refresh_property: tuple[str, object] | None = None,
        on_refresh: Callable[[], None] | None = None,
    ):
        super().__init__()
        self.setObjectName(object_name)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(18, 16, 18, 16)
        self._layout.setSpacing(8)

        self.clock_label = QLabel()
        self.clock_label.setObjectName("timeCardClock")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.date_label = QLabel()
        self.date_label.setObjectName("timeCardDate")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.last_update_label = QLabel("마지막 업데이트: -")
        self.last_update_label.setObjectName("mutedText")
        self.last_update_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.last_update_label.setHidden(not show_last_update)

        self.status_label = QLabel(status_text)
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)
        self.status_label.setHidden(not bool(status_text))

        self._layout.addWidget(self.clock_label)
        self._layout.addWidget(self.date_label)
        self._layout.addWidget(self.last_update_label)
        self._layout.addWidget(self.status_label)

        self.refresh_button = None
        if refresh_text is not None:
            self.refresh_button = QPushButton(refresh_text)
            self.refresh_button.setObjectName("secondaryButton")
            if refresh_property is not None:
                self.refresh_button.setProperty(*refresh_property)
            if on_refresh is not None:
                self.refresh_button.clicked.connect(on_refresh)
            self._layout.addWidget(self.refresh_button)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_clock)
        self._timer.start(1000)
        self.update_clock()

    def add_action(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setHidden(not bool(message))

    def mark_updated(self, source: str = "") -> None:
        current_time = QDateTime.currentDateTime().toString("HH:mm:ss")
        suffix = f" ({source})" if source else ""
        self.last_update_label.setText(f"마지막 업데이트: {current_time}{suffix}")
        self.last_update_label.setHidden(False)

    def update_clock(self) -> None:
        now = QDateTime.currentDateTime()
        self.clock_label.setText(now.toString("HH:mm:ss"))
        self.date_label.setText(now.toString("yyyy.MM.dd"))


class AdminSidebar(QFrame):
    nav_requested = pyqtSignal(str)

    def __init__(
        self,
        nav_items: Sequence[NavItem],
        user_name: str,
        user_role: str = "요양보호사",
        on_logout: Callable[[], None] | None = None,
    ):
        super().__init__()
        self.setObjectName("adminSidebar")
        self._buttons: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        brand = QLabel("ROPI")
        brand.setObjectName("sidebarBrand")
        subtitle = QLabel("관리자 콘솔")
        subtitle.setObjectName("sidebarSubtitle")

        root.addWidget(brand)
        root.addWidget(subtitle)

        for key, label in nav_items:
            button = QPushButton(label)
            button.setObjectName("sideButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, nav_key=key: self._request_nav(nav_key)
            )
            self._buttons[key] = button
            root.addWidget(button)

        root.addStretch()

        user_box = QFrame()
        user_box.setObjectName("userBox")
        user_layout = QVBoxLayout(user_box)
        user_layout.setContentsMargins(14, 14, 14, 14)
        user_layout.setSpacing(4)

        user_label = QLabel(user_name)
        user_label.setObjectName("userName")
        role_label = QLabel(user_role)
        role_label.setObjectName("mutedText")

        user_layout.addWidget(user_label)
        user_layout.addWidget(role_label)

        logout_button = QPushButton("로그아웃")
        logout_button.setObjectName("dangerButton")
        if on_logout is not None:
            logout_button.clicked.connect(on_logout)

        root.addWidget(user_box)
        root.addWidget(logout_button)

    def button(self, key: str) -> QPushButton:
        return self._buttons[key]

    def set_active(self, key: str) -> None:
        for nav_key, button in self._buttons.items():
            button.setChecked(nav_key == key)

    def _request_nav(self, key: str) -> None:
        self.set_active(key)
        self.nav_requested.emit(key)


class AdminShell(QWidget):
    nav_requested = pyqtSignal(str)
    page_changed = pyqtSignal(str)

    def __init__(
        self,
        nav_items: Sequence[NavItem],
        user_name: str,
        user_role: str = "요양보호사",
        on_logout: Callable[[], None] | None = None,
    ):
        super().__init__()
        self.setObjectName("adminShell")
        self._pages: dict[str, QWidget] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = AdminSidebar(
            nav_items=nav_items,
            user_name=user_name,
            user_role=user_role,
            on_logout=on_logout,
        )
        self.sidebar.nav_requested.connect(self.nav_requested.emit)

        self.stack = QStackedWidget()
        self.stack.setObjectName("adminPageStack")

        self.page_scroll = QScrollArea()
        self.page_scroll.setObjectName("adminPageScroll")
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.page_scroll.setWidget(self.stack)

        root.addWidget(self.sidebar)
        root.addWidget(self.page_scroll, 1)

    def add_page(self, key: str, page: QWidget) -> None:
        if key in self._pages:
            return
        self._pages[key] = page
        self.stack.addWidget(page)

    def has_page(self, key: str) -> bool:
        return key in self._pages

    def page(self, key: str) -> QWidget:
        return self._pages[key]

    def set_page(self, key: str) -> None:
        page = self._pages[key]
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active(key)
        self.page_scroll.verticalScrollBar().setValue(0)
        self.page_changed.emit(key)


class PlaceholderPage(QWidget):
    def __init__(self, title: str, subtitle: str, show_status: bool = False):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 34, 34, 34)
        root.setSpacing(18)

        header_row = QHBoxLayout()
        header_row.setSpacing(16)
        header_row.addWidget(
            PageHeader(title=title, subtitle=subtitle, show_status=show_status),
            1,
        )
        header_row.addWidget(PageTimeCard(show_last_update=False))
        root.addLayout(header_row)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(8)

        message = QLabel("이 화면은 공통 shell 적용 후 단계적으로 구현합니다.")
        message.setObjectName("sectionTitle")
        detail = QLabel("현재 단계에서는 내비게이션 구조와 페이지 진입 계약만 고정합니다.")
        detail.setObjectName("mutedText")

        card_layout.addWidget(message)
        card_layout.addWidget(detail)
        root.addWidget(card)
        root.addStretch()


__all__ = [
    "AdminShell",
    "AdminSidebar",
    "NavItem",
    "PageHeader",
    "PageTimeCard",
    "PlaceholderPage",
    "SystemStatusStrip",
]
