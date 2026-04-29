from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
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
        "Control Service": "unknown",
        "DB": "unknown",
        "ROS2": "unknown",
        "AI Server": "unknown",
    }

    _STATUS_TEXT = {
        "online": "정상",
        "warning": "주의",
        "error": "오류",
        "offline": "오류",
        "unknown": "확인 중",
    }

    _STATUS_OBJECT_NAME = {
        "online": "systemStatusOnline",
        "warning": "systemStatusWarning",
        "error": "systemStatusError",
        "offline": "systemStatusError",
        "unknown": "systemStatusUnknown",
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
    ):
        super().__init__()
        self.setObjectName("pageHeader")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
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

        self.status_strip = SystemStatusStrip(statuses)

        root.addLayout(title_box, 1)
        root.addWidget(self.status_strip, 0, Qt.AlignmentFlag.AlignTop)

    def set_text(self, title: str, subtitle: str = "") -> None:
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)


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
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(34, 34, 34, 34)
        root.setSpacing(18)

        root.addWidget(PageHeader(title=title, subtitle=subtitle))

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
    "PlaceholderPage",
    "SystemStatusStrip",
]
