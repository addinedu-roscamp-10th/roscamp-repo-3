from PyQt6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QWidget, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer

def make_card(title: str, chip: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    root = QVBoxLayout(frame)
    head = QHBoxLayout()
    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")
    head.addWidget(title_label)
    head.addStretch()
    if chip:
        chip_label = QLabel(chip)
        chip_label.setProperty("chip", True)
        head.addWidget(chip_label)
    root.addLayout(head)
    return frame, root

def make_stat_box(label: str, value: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("statBox")
    layout = QVBoxLayout(frame)
    s1 = QLabel(label)
    s1.setObjectName("muted")
    s2 = QLabel(value)
    s2.setObjectName("statValue")
    layout.addWidget(s1)
    layout.addWidget(s2)
    return frame

def page_title(title: str, subtitle: str = "") -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    layout.addWidget(t)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    return box


class InlineStatusMixin:
    def init_inline_status(self) -> QLabel:
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        return self.status_label

    def show_inline_status(self, text: str, level: str = "info") -> None:
        color_map = {
            "info": "#1f4db8",
            "success": "#1f7a3d",
            "warning": "#b26a00",
            "error": "#c0392b",
        }
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color_map.get(level, '#1f4db8')}; font-weight: 600;"
        )
        self.status_label.show()
        QTimer.singleShot(4000, self.hide_inline_status)

    def hide_inline_status(self) -> None:
        if hasattr(self, "status_label"):
            self.status_label.hide()
