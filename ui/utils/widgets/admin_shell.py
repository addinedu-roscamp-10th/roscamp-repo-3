from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from PyQt6.QtCore import QDateTime, QSize, Qt, QTimer, pyqtSignal
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
ADMIN_SIDEBAR_WIDTH = 240
PAGE_TIME_CARD_WIDTH = 340
PAGE_TIME_CARD_HEIGHT = 174
PAGE_TIME_CARD_ACTION_ROW_HEIGHT = 44
PAGE_TIME_CARD_CLOCK_ROW_HEIGHT = 30
PAGE_TIME_CARD_META_ROW_HEIGHT = 16
PAGE_TIME_CARD_STATUS_ROW_HEIGHT = 18
PAGE_TIME_CARD_BUTTON_HEIGHT = 42


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
        self.setFixedSize(PAGE_TIME_CARD_WIDTH, PAGE_TIME_CARD_HEIGHT)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 10, 16, 10)
        self._layout.setSpacing(3)

        self.clock_label = QLabel()
        self.clock_label.setObjectName("timeCardClock")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.clock_label.setFixedHeight(PAGE_TIME_CARD_CLOCK_ROW_HEIGHT)

        self.date_label = QLabel()
        self.date_label.setObjectName("timeCardDate")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date_label.setFixedHeight(PAGE_TIME_CARD_META_ROW_HEIGHT)

        self.last_update_label = QLabel(
            "마지막 업데이트: -" if show_last_update else " "
        )
        self.last_update_label.setObjectName("mutedText")
        self.last_update_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.last_update_label.setFixedHeight(PAGE_TIME_CARD_META_ROW_HEIGHT)

        self.status_label = QLabel(status_text or " ")
        self.status_label.setObjectName("mutedText")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.status_label.setWordWrap(False)
        self.status_label.setFixedHeight(PAGE_TIME_CARD_STATUS_ROW_HEIGHT)

        self._layout.addWidget(self.clock_label)
        self._layout.addWidget(self.date_label)
        self._layout.addWidget(self.last_update_label)
        self._layout.addWidget(self.status_label)

        self.action_row = QWidget()
        self.action_row.setObjectName("timeCardActionRow")
        self.action_row.setFixedHeight(PAGE_TIME_CARD_ACTION_ROW_HEIGHT)
        self.action_layout = QHBoxLayout(self.action_row)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(8)
        self.action_layout.addStretch(1)
        self._layout.addWidget(self.action_row)

        self.refresh_button = None
        if refresh_text is not None:
            self.refresh_button = QPushButton(refresh_text)
            self.refresh_button.setObjectName("secondaryButton")
            if refresh_property is not None:
                self.refresh_button.setProperty(*refresh_property)
            if on_refresh is not None:
                self.refresh_button.clicked.connect(on_refresh)
            self.add_action(self.refresh_button)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_clock)
        self._timer.start(1000)
        self.update_clock()

    def add_action(self, widget: QWidget) -> None:
        widget.setFixedHeight(PAGE_TIME_CARD_BUTTON_HEIGHT)
        self.action_layout.insertWidget(
            max(0, self.action_layout.count() - 1),
            widget,
        )

    def sizeHint(self) -> QSize:
        return QSize(PAGE_TIME_CARD_WIDTH, PAGE_TIME_CARD_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def set_status(self, message: str) -> None:
        text = str(message or "").strip()
        self.status_label.setText(text or " ")
        self.status_label.setToolTip(text)

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
        user_role: str = "관제 운영자",
        on_logout: Callable[[], None] | None = None,
    ):
        super().__init__()
        self.setObjectName("adminSidebar")
        self.setFixedWidth(ADMIN_SIDEBAR_WIDTH)
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


class AdminPageStack(QStackedWidget):
    def __init__(self):
        super().__init__()
        self._page_scrolls: dict[QWidget, QScrollArea] = {}
        self._scroll_pages: dict[QScrollArea, QWidget] = {}

    def add_page(self, page: QWidget) -> QScrollArea:
        existing_scroll = self._page_scrolls.get(page)
        if existing_scroll is not None:
            return existing_scroll

        scroll = QScrollArea()
        scroll.setObjectName("adminPageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)

        self._page_scrolls[page] = scroll
        self._scroll_pages[scroll] = page
        super().addWidget(scroll)
        return scroll

    def setCurrentWidget(self, widget: QWidget) -> None:
        target = self._page_scrolls.get(widget, widget)
        super().setCurrentWidget(target)

    def currentWidget(self) -> QWidget | None:
        current = super().currentWidget()
        return self._scroll_pages.get(current, current)

    def current_scroll_area(self) -> QScrollArea | None:
        current = super().currentWidget()
        if isinstance(current, QScrollArea):
            return current
        return None


class AdminShell(QWidget):
    nav_requested = pyqtSignal(str)
    page_changed = pyqtSignal(str)

    def __init__(
        self,
        nav_items: Sequence[NavItem],
        user_name: str,
        user_role: str = "관제 운영자",
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

        self.stack = AdminPageStack()
        self.stack.setObjectName("adminPageStack")
        self.page_scroll = None

        root.addWidget(self.sidebar)
        root.addWidget(self.stack, 1)

    def add_page(self, key: str, page: QWidget) -> None:
        if key in self._pages:
            return
        self._pages[key] = page
        self.stack.add_page(page)

    def has_page(self, key: str) -> bool:
        return key in self._pages

    def page(self, key: str) -> QWidget:
        return self._pages[key]

    def set_page(self, key: str) -> None:
        page = self._pages[key]
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active(key)
        self.page_scroll = self.stack.current_scroll_area()
        if self.page_scroll is not None:
            self.page_scroll.verticalScrollBar().setValue(0)
        self.page_changed.emit(key)


__all__ = [
    "AdminPageStack",
    "AdminShell",
    "AdminSidebar",
    "NavItem",
    "PageHeader",
    "PageTimeCard",
    "SystemStatusStrip",
]
