import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QWidget


_APP = None
_LEAKED_WIDGETS = []


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_1_qt_harness_selftest_leaves_top_level_widget_for_fixture_cleanup():
    _app()

    widget = QWidget()
    widget.setObjectName("qtHarnessSelfTestLeakedWidget")
    widget.show()
    _LEAKED_WIDGETS.append(widget)

    assert widget.isHidden() is False


def test_2_qt_harness_selftest_starts_after_widget_cleanup():
    _app()

    leaked_widgets = [
        widget
        for widget in QApplication.topLevelWidgets()
        if widget.objectName() == "qtHarnessSelfTestLeakedWidget"
        and not widget.isHidden()
    ]

    assert leaked_widgets == []
