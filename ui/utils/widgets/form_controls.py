from collections.abc import Callable, Mapping

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QCompleter,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)


def configure_searchable_combo(combo: QComboBox, placeholder: str) -> QComboBox:
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    combo.lineEdit().setPlaceholderText(placeholder)

    completer = QCompleter(combo.model(), combo)
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    completer.setFilterMode(Qt.MatchFlag.MatchContains)
    combo.setCompleter(completer)
    return combo


def make_field_group(
    label_text: str,
    widget: QWidget,
    object_name: str = "formFieldGroup",
    spacing: int = 6,
) -> QFrame:
    group = QFrame()
    group.setObjectName(object_name)
    group.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Fixed,
    )

    layout = QVBoxLayout(group)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)

    label = QLabel(label_text)
    label.setObjectName("fieldLabel")
    label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    label.setSizePolicy(
        QSizePolicy.Policy.Preferred,
        QSizePolicy.Policy.Fixed,
    )

    layout.addWidget(label)
    layout.addWidget(widget)
    return group


def create_priority_segment(
    code_to_label: Mapping[str, str],
    on_selected: Callable[[str], None] | None = None,
    parent: QWidget | None = None,
) -> tuple[QFrame, QButtonGroup, dict[str, QPushButton]]:
    segment = QFrame()
    segment.setObjectName("prioritySegment")
    layout = QHBoxLayout(segment)
    layout.setContentsMargins(4, 4, 4, 4)
    layout.setSpacing(6)

    button_group = QButtonGroup(parent)
    button_group.setExclusive(True)
    buttons: dict[str, QPushButton] = {}

    for code, label in code_to_label.items():
        button = QPushButton(label)
        button.setObjectName("prioritySegmentButton")
        button.setCheckable(True)
        if on_selected is not None:
            button.clicked.connect(
                lambda _checked=False, priority=code: on_selected(priority)
            )
        buttons[code] = button
        button_group.addButton(button)
        layout.addWidget(button)

    return segment, button_group, buttons
