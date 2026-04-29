import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QComboBox, QPushButton


_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_form_controls_build_searchable_combo_field_group_and_priority_segment():
    _app()

    from ui.utils.widgets.form_controls import (
        configure_searchable_combo,
        create_priority_segment,
        make_field_group,
    )

    combo = QComboBox()
    configure_searchable_combo(combo, "물품 검색")

    assert combo.isEditable() is True
    assert combo.lineEdit().placeholderText() == "물품 검색"
    assert combo.completer() is not None

    field_group = make_field_group("운반 물품", combo)
    assert field_group.objectName() == "formFieldGroup"
    assert field_group.findChild(QLabel).text() == "운반 물품"

    selected = []
    segment, button_group, buttons = create_priority_segment(
        {
            "NORMAL": "일반",
            "URGENT": "긴급",
            "HIGHEST": "최우선",
        },
        on_selected=selected.append,
    )

    assert segment.objectName() == "prioritySegment"
    assert button_group.exclusive() is True
    assert list(buttons.keys()) == ["NORMAL", "URGENT", "HIGHEST"]
    assert [
        button.text()
        for button in segment.findChildren(QPushButton)
        if button.objectName() == "prioritySegmentButton"
    ] == ["일반", "긴급", "최우선"]

    buttons["URGENT"].click()
    assert selected == ["URGENT"]


def test_task_request_forms_do_not_depend_on_each_other_for_common_controls():
    source = open("ui/utils/pages/caregiver/task_request_page.py").read()

    assert "DeliveryRequestForm._configure_searchable_combo" not in source
    assert "DeliveryRequestForm._field_group" not in source
