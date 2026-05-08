import sys
from pathlib import Path
from uuid import uuid4

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
from ui.kiosk_ui.staff_call_modal import KioskStaffCallModal  # noqa: E402
from ui.utils.core.styles import load_stylesheet  # noqa: E402
from ui.utils.network.service_clients import StaffCallRemoteService  # noqa: E402


KIOSK_ID = "lobby_kiosk_01"


class KioskHomeWindow(QMainWindow):
    def __init__(self, *, staff_call_service=None):
        super().__init__()
        self.setWindowTitle("ROPI Kiosk")
        self.resize(1440, 960)
        self.staff_call_service = staff_call_service or StaffCallRemoteService()
        self.kiosk_id = KIOSK_ID
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
        context = self._staff_call_context()
        try:
            response = self.staff_call_service.submit_staff_call(
                call_type="직원 호출",
                description=self._staff_call_description(source_screen, context),
                idempotency_key=f"kiosk_staff_call_{uuid4().hex}",
                visitor_id=context.get("visitor_id"),
                member_id=context.get("member_id"),
                kiosk_id=self.kiosk_id,
            )
        except Exception as exc:
            self._show_staff_call_modal(
                success=False,
                message=f"서버 연결 중 오류가 발생했습니다: {exc}",
            )
            return

        success = (response or {}).get("result_code") == "ACCEPTED"
        self._show_staff_call_modal(
            success=success,
            message=(
                (response or {}).get("result_message")
                or ("직원이 곧 도착합니다." if success else "데스크에 문의해 주세요.")
            ),
        )

    def _staff_call_context(self):
        current_patient = self.current_patient
        if self.stack.currentWidget() is self.confirmation_page:
            current_patient = self.confirmation_page.selected_patient
        elif self.stack.currentWidget() is self.progress_page:
            current_patient = self.progress_page.selected_patient

        visitor_id = self._normalize_optional_id(
            (current_patient or {}).get("visitor_id")
            or (self.current_visitor_session or {}).get("visitor_id")
        )
        member_id = self._normalize_optional_id(
            (current_patient or {}).get("member_id")
            or (self.current_visitor_session or {}).get("member_id")
        )
        return {
            "visitor_id": visitor_id,
            "member_id": member_id,
            "name": str((current_patient or {}).get("name") or "").strip(),
            "room": str((current_patient or {}).get("room") or "").strip(),
        }

    def _staff_call_description(self, source_screen, context):
        parts = [f"{source_screen}에서 직원 호출을 요청했습니다."]
        if context.get("name"):
            parts.append(f"대상={context['name']}")
        if context.get("room"):
            parts.append(f"호실={context['room']}")
        if context.get("visitor_id"):
            parts.append(f"visitor_id={context['visitor_id']}")
        if context.get("member_id"):
            parts.append(f"member_id={context['member_id']}")
        return " ".join(parts)

    def _show_staff_call_modal(self, *, success, message):
        self._sync_staff_call_modal_geometry()
        self.staff_call_modal.show_result(success=success, message=message)

    def _sync_staff_call_modal_geometry(self):
        if hasattr(self, "staff_call_modal") and self.centralWidget() is not None:
            self.staff_call_modal.setGeometry(self.centralWidget().rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_staff_call_modal_geometry()

    @staticmethod
    def _normalize_optional_id(value):
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        try:
            normalized = int(raw)
        except (TypeError, ValueError):
            return None
        return normalized if normalized > 0 else None


__all__ = ["KioskHomeWindow", "KioskVisitorRegistrationPage", "load_stylesheet"]


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())

    window = KioskHomeWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
