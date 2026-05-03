from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout


CHIP_OBJECT_NAMES = {
    "green": "chipGreen",
    "blue": "chipBlue",
    "red": "chipRed",
    "yellow": "chipYellow",
}


def display_text(value, default="-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def int_value(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def battery_text(value) -> str:
    if value is None or value == "":
        return "-"
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return str(value)


class StatusChip(QLabel):
    def __init__(self, text: str, chip_type: str = "blue"):
        super().__init__(text)
        self.setObjectName(CHIP_OBJECT_NAMES.get(chip_type, "chipBlue"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class SummaryCard(QFrame):
    def __init__(self, title: str, *, initial_value: str = "0"):
        super().__init__()
        self.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("mutedText")

        self.value_label = QLabel(initial_value)
        self.value_label.setObjectName("summaryValue")

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value, unit: str = ""):
        self.value_label.setText(f"{value}{unit}")


__all__ = [
    "StatusChip",
    "SummaryCard",
    "battery_text",
    "display_text",
    "int_value",
]
