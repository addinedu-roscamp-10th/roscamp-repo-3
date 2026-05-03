import os
import tomllib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_kiosk_console_script_is_registered():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    assert data["project"]["scripts"]["ropi-kiosk-ui"] == "ui.kiosk_ui.main:main"


def test_kiosk_window_entrypoint_builds_home_window():
    _app()

    from ui.kiosk_ui.main_window import KioskHomeWindow

    window = KioskHomeWindow()

    try:
        assert window.windowTitle() == "ROPI Kiosk"
        assert window.stack.count() >= 4
        assert window.stack.currentWidget() is window.home_page
    finally:
        window.close()
