import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


_APP = None
REPO_ROOT = Path(__file__).resolve().parents[3]
CAREGIVER_PAGE_ROOT = REPO_ROOT / "ui" / "utils" / "pages" / "caregiver"


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_admin_common_display_helpers_and_widgets():
    _app()

    from ui.utils.widgets.admin_common import (
        KeyValueList,
        KeyValueRow,
        StatusChip,
        SummaryCard,
        battery_text,
        display_text,
        int_value,
        operator_datetime_text,
    )

    assert display_text(None) == "-"
    assert display_text("  ") == "-"
    assert display_text(" pinky2 ") == "pinky2"
    assert int_value("7") == 7
    assert int_value("bad") == 0
    assert battery_text(87.5) == "88%"
    assert battery_text(None) == "-"
    assert operator_datetime_text("2026-05-03T12:00:00") == "2026.05.03 12:00"
    assert operator_datetime_text("2026-05-03T12:00:00.123Z") == "2026.05.03 12:00"
    assert operator_datetime_text("2026-05-03") == "2026.05.03"
    assert operator_datetime_text("not a date") == "not a date"

    summary = SummaryCard("전체 로봇", initial_value="0대")
    summary.set_value(3, "대")
    chip = StatusChip("ONLINE", "green")
    key_value = KeyValueRow("로봇", "pinky2")
    key_value_list = KeyValueList("표시할 정보가 없습니다.")
    key_value_list.set_rows([("상태", "ONLINE"), ("배터리", "88%")])

    try:
        assert summary.value_label.text() == "3대"
        assert chip.objectName() == "chipGreen"
        assert key_value.objectName() == "keyValueRow"
        assert key_value.key_label.objectName() == "keyValueKey"
        assert key_value.key_label.text() == "로봇"
        assert key_value.value_label.objectName() == "keyValueValue"
        assert key_value.value_label.text() == "pinky2"
        assert key_value_list.objectName() == "keyValueList"
        assert [row.key_label.text() for row in key_value_list._rows] == [
            "상태",
            "배터리",
        ]
    finally:
        summary.close()
        chip.close()
        key_value.close()
        key_value_list.close()


def test_recent_admin_pages_use_common_display_widgets():
    common_import = "from ui.utils.widgets.admin_common import"
    page_names = [
        "home_dashboard_page.py",
        "robot_status_page.py",
        "alert_log_page.py",
        "inventory_management_page.py",
    ]

    for page_name in page_names:
        source = (CAREGIVER_PAGE_ROOT / page_name).read_text(encoding="utf-8")
        assert common_import in source
        assert "class SummaryCard" not in source
        assert "class StatusChip" not in source
        assert "def _display(" not in source
