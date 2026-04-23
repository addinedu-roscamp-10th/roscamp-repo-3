import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.admin_ui.login_role_window import LoginRoleWindow
from ui.utils.core.paths import STYLE_PATH


def load_stylesheet() -> str:
    try:
        return STYLE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())

    window = LoginRoleWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
