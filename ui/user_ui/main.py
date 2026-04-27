import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.user_ui.main_window import VisitorMainWindow, load_stylesheet


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())

    window = VisitorMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
