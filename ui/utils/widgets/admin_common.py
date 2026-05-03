from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


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


class KeyValueRow(QFrame):
    def __init__(
        self,
        key: str,
        value: str = "-",
        *,
        row_object_name: str = "keyValueRow",
        key_object_name: str = "keyValueKey",
        value_object_name: str = "keyValueValue",
        align_value: bool = True,
    ):
        super().__init__()
        self.setObjectName(row_object_name)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.key_label = QLabel(display_text(key))
        self.key_label.setObjectName(key_object_name)

        self.value_label = QLabel(display_text(value))
        self.value_label.setObjectName(value_object_name)
        self.value_label.setWordWrap(True)
        if align_value:
            self.value_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

        layout.addWidget(self.key_label)
        layout.addStretch(1)
        layout.addWidget(self.value_label)

    def set_value(self, value) -> None:
        self.value_label.setText(display_text(value))


class KeyValueList(QFrame):
    def __init__(self, empty_text: str = "-"):
        super().__init__()
        self.setObjectName("keyValueList")
        self._empty_text = empty_text
        self._rows: list[KeyValueRow | QLabel] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self.set_rows([])

    def set_rows(self, rows, *, empty_text: str | None = None) -> None:
        self._clear()
        if empty_text is not None:
            self._empty_text = empty_text
        normalized_rows = [
            (display_text(key), display_text(value))
            for key, value in (rows or [])
            if display_text(key, "") != ""
        ]
        if not normalized_rows:
            placeholder = QLabel(self._empty_text)
            placeholder.setObjectName("mutedText")
            placeholder.setWordWrap(True)
            self._layout.addWidget(placeholder)
            self._rows.append(placeholder)
            return

        for key, value in normalized_rows:
            row = KeyValueRow(key, value)
            self._layout.addWidget(row)
            self._rows.append(row)

    def _clear(self) -> None:
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows = []


def make_key_value_row(
    key: str,
    value: str = "-",
    *,
    row_object_name: str = "keyValueRow",
    key_object_name: str = "keyValueKey",
    value_object_name: str = "keyValueValue",
):
    row = KeyValueRow(
        key,
        value,
        row_object_name=row_object_name,
        key_object_name=key_object_name,
        value_object_name=value_object_name,
    )
    return row, row.key_label, row.value_label


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
    "KeyValueList",
    "KeyValueRow",
    "StatusChip",
    "SummaryCard",
    "battery_text",
    "display_text",
    "int_value",
    "make_key_value_row",
]
