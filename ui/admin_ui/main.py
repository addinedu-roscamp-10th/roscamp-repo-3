import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.admin_ui.login_auth_window import LoginAuthWindow
from ui.utils.core.styles import load_stylesheet


def create_initial_window():
    return LoginAuthWindow(role="caregiver")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())

    window = create_initial_window()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
