from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


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


__all__ = [
    "KioskActionIconGlyph",
    "KioskFooterStat",
    "KioskHomeActionCard",
    "KioskHomePage",
]
