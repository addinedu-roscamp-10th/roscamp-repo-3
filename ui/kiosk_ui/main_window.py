import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.kiosk_ui.guide_confirmation_page import KioskGuideConfirmationPage  # noqa: E402
from ui.kiosk_ui.guide_progress_page import KioskRobotGuidanceProgressPage  # noqa: E402
from ui.kiosk_ui.home_page import KioskHomePage  # noqa: E402
from ui.kiosk_ui.registration_page import KioskVisitorRegistrationPage  # noqa: E402
from ui.kiosk_ui.staff_call_controller import KioskStaffCallController  # noqa: E402
from ui.kiosk_ui.staff_call_modal import KioskStaffCallModal  # noqa: E402
from ui.utils.core.styles import load_stylesheet  # noqa: E402


KIOSK_ID = "lobby_kiosk_01"


class KioskHomeWindow(QMainWindow):
    def __init__(self, *, staff_call_service=None):
        super().__init__()
        self.setWindowTitle("ROPI Kiosk")
        self.resize(1440, 960)
        self.kiosk_id = KIOSK_ID
        self.staff_call_controller = KioskStaffCallController(
            staff_call_service=staff_call_service,
            kiosk_id=self.kiosk_id,
        )
        self.current_patient = None
        self.current_visitor_session = None
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("kioskRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.home_page = KioskHomePage()
        self.registration_page = KioskVisitorRegistrationPage(
            go_home_page=self._show_home_page,
            go_confirmation_page=self._show_confirmation_page,
            go_back_page=self._show_home_page,
        )
        self.confirmation_page = KioskGuideConfirmationPage(
            go_home_page=self._show_home_page,
            go_back_page=lambda: self.stack.setCurrentWidget(self.registration_page),
            go_progress_page=self._show_progress_page,
        )
        self.progress_page = KioskRobotGuidanceProgressPage(
            go_home_page=self._show_home_page,
        )

        self.home_page.register_card.clicked.connect(
            lambda: self._show_registration_page(focus_resident_search=False)
        )
        self.home_page.call_card.clicked.connect(
            lambda: self._submit_staff_call("홈 화면")
        )
        self.registration_page.call_staff_button.clicked.connect(
            lambda: self._submit_staff_call("방문자 등록 화면")
        )
        self.confirmation_page.call_staff_button.clicked.connect(
            lambda: self._submit_staff_call("안내 화면")
        )
        self.progress_page.call_staff_button.clicked.connect(
            lambda: self._submit_staff_call("안내 진행 화면")
        )

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.registration_page)
        self.stack.addWidget(self.confirmation_page)
        self.stack.addWidget(self.progress_page)
        root_layout.addWidget(self.stack)
        self.staff_call_modal = KioskStaffCallModal(root)
        self.setCentralWidget(root)
        self._sync_staff_call_modal_geometry()

    def _show_home_page(self):
        self.current_patient = None
        self.current_visitor_session = None
        self.progress_page._clear_guide_screen_session()
        self.stack.setCurrentWidget(self.home_page)

    def _show_registration_page(self, *, focus_resident_search=False):
        self.current_patient = None
        self.current_visitor_session = None
        self.registration_page.reset_form()
        self.stack.setCurrentWidget(self.registration_page)
        if focus_resident_search:
            self.registration_page.resident_search_input.setFocus()
            return
        self.registration_page.visitor_name_input.setFocus()

    def _show_confirmation_page(self, patient):
        self.current_patient = patient or None
        self.current_visitor_session = {
            "visitor_id": (patient or {}).get("visitor_id"),
            "member_id": (patient or {}).get("member_id"),
        }
        self.confirmation_page.set_patient(patient)
        self.stack.setCurrentWidget(self.confirmation_page)

    def _show_progress_page(self, patient, session=None):
        self.current_patient = patient or None
        self.current_visitor_session = {
            "visitor_id": (patient or {}).get("visitor_id"),
            "member_id": (patient or {}).get("member_id"),
        }
        self.progress_page.set_patient(patient, session=session)
        self.stack.setCurrentWidget(self.progress_page)

    def _submit_staff_call(self, source_screen):
        result = self.staff_call_controller.submit(
            source_screen=source_screen,
            current_patient=self.current_patient,
            current_visitor_session=self.current_visitor_session,
            selected_patient=self._current_staff_call_patient(),
        )
        self._show_staff_call_modal(
            success=result.success,
            message=result.message,
        )

    def _current_staff_call_patient(self):
        if self.stack.currentWidget() is self.confirmation_page:
            return self.confirmation_page.selected_patient
        if self.stack.currentWidget() is self.progress_page:
            return self.progress_page.selected_patient
        return None

    def _show_staff_call_modal(self, *, success, message):
        self._sync_staff_call_modal_geometry()
        self.staff_call_modal.show_result(success=success, message=message)

    def _sync_staff_call_modal_geometry(self):
        if hasattr(self, "staff_call_modal") and self.centralWidget() is not None:
            self.staff_call_modal.setGeometry(self.centralWidget().rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_staff_call_modal_geometry()


__all__ = ["KioskHomeWindow", "KioskVisitorRegistrationPage", "load_stylesheet"]


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())

    window = KioskHomeWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
