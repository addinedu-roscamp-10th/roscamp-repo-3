import os
import tomllib
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QWidget


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _visible_texts(widget) -> list[str]:
    texts: list[str] = []
    for label in widget.findChildren(QLabel):
        texts.append(label.text())
    for button in widget.findChildren(QPushButton):
        texts.append(button.text())
    return texts


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
        assert window.registration_page.objectName() == "kioskVisitorRegistrationPage"
        assert window.confirmation_page.objectName() == "kioskGuideConfirmationPage"
        assert window.progress_page.objectName() == "kioskProgressPage"
    finally:
        window.close()


def test_kiosk_home_ports_wireframe_style_without_english_or_duplicate_cta():
    _app()

    from ui.kiosk_ui.main_window import KioskHomeWindow

    window = KioskHomeWindow()

    try:
        home = window.home_page
        texts = _visible_texts(home)

        assert home.findChild(QFrame, "kioskHomeCanvas") is not None
        assert home.findChild(QLabel, "kioskBrandIcon") is not None
        assert "ROPI 요양보호 서비스" in texts
        assert "무엇을 도와드릴까요?" in texts
        assert "어르신 찾기" not in texts
        assert "방문 등록" in texts
        assert "직원 호출" in texts
        assert "현재 위치" in texts
        assert "방문 가능 시간" in texts
        assert "안내 로봇 상태" in texts

        forbidden_fragments = [
            "Nursing Care Assistant",
            "Call Staff",
            "Current Location",
            "Hours:",
            "Robot:",
            "선택",
            "도움말",
            "한국어",
            "필요한 서비스를",
        ]
        for forbidden in forbidden_fragments:
            assert all(forbidden not in text for text in texts)
        for forbidden_label in ["찾기", "등록", "호출"]:
            assert forbidden_label not in texts

        cards = home.findChildren(QFrame, "kioskActionCard")
        assert len(cards) == 2
        assert all(card.minimumHeight() >= 380 for card in cards)
        assert all(not card.findChildren(QPushButton) for card in cards)
        assert len(home.findChildren(QFrame, "kioskCardAccent")) == 0
        assert len(home.findChildren(QWidget, "kioskActionIconGlyph")) == 2
        assert not hasattr(home, "search_card")
    finally:
        window.close()


def test_kiosk_home_routes_visit_registration_to_registration():
    _app()

    from ui.kiosk_ui.main_window import KioskHomeWindow

    window = KioskHomeWindow()

    try:
        window.home_page.register_card.clicked.emit()
        assert window.stack.currentWidget() is window.registration_page
    finally:
        window.close()


def test_kiosk_visitor_registration_embeds_resident_lookup_and_visit_registration():
    _app()

    from ui.kiosk_ui.main_window import KioskVisitorRegistrationPage

    class FakeKioskVisitorService:
        def __init__(self):
            self.lookup_calls = []
            self.register_calls = []

        def lookup_residents(self, *, keyword, limit=10):
            self.lookup_calls.append({"keyword": keyword, "limit": limit})
            return {
                "result_code": "FOUND",
                "result_message": "어르신 정보를 확인했습니다.",
                "reason_code": None,
                "matches": [
                    {
                        "member_id": 1,
                        "display_name": "김*수",
                        "birth_date": "1942-03-14",
                        "room_no": "301",
                        "visit_available": True,
                        "guide_available": True,
                    }
                ],
            }

        def register_visit(
            self,
            *,
            visitor_name,
            phone_no,
            relationship,
            visit_purpose,
            target_member_id,
            privacy_agreed,
            kiosk_id=None,
        ):
            self.register_calls.append(
                {
                    "visitor_name": visitor_name,
                    "phone_no": phone_no,
                    "relationship": relationship,
                    "visit_purpose": visit_purpose,
                    "target_member_id": target_member_id,
                    "privacy_agreed": privacy_agreed,
                    "kiosk_id": kiosk_id,
                }
            )
            return {
                "result_code": "REGISTERED",
                "result_message": "방문 등록이 완료되었습니다.",
                "reason_code": None,
                "visitor_id": 42,
                "member_id": 1,
                "resident_name": "김영수",
                "room_no": "301",
                "visit_status": "면회 가능",
            }

    service = FakeKioskVisitorService()
    routed_patients = []
    page = KioskVisitorRegistrationPage(
        service=service,
        go_confirmation_page=routed_patients.append,
    )

    try:
        assert page.objectName() == "kioskVisitorRegistrationPage"
        assert page.findChild(QFrame, "kioskRegistrationCanvas") is not None
        assert page.search_button.isEnabled() is False
        assert page.register_button.isEnabled() is False
        assert page.selected_visit_purpose is None
        assert len(page.purpose_cards) == 4
        assert page.findChild(QLabel, "kioskSearchStatusText") is None
        assert all(card.minimumHeight() >= 96 for card in page.purpose_cards.values())
        assert all(card.maximumHeight() == 96 for card in page.purpose_cards.values())
        assert all(
            input_widget.minimumHeight() >= 64
            for input_widget in [
                page.visitor_name_input,
                page.phone_input,
                page.relationship_input,
                page.resident_search_input,
            ]
        )
        assert all(
            input_widget.maximumHeight() >= 72
            for input_widget in [
                page.visitor_name_input,
                page.phone_input,
                page.relationship_input,
                page.resident_search_input,
            ]
        )
        assert "방문자 정보와 개인정보 동의" not in " ".join(_visible_texts(page))

        page.visitor_name_input.setText(" 김민수 ")
        page.phone_input.setText(" 010-1111-2222 ")
        page.relationship_input.setText(" 아들 ")
        page.select_visit_purpose("family")
        page.privacy_checkbox.setChecked(True)
        page.resident_search_input.setText(" 김영수 ")

        assert page.search_button.isEnabled() is True
        assert page.selected_visit_purpose == "가족 면회"
        assert page.purpose_cards["family"].property("selected") is True

        page.search_resident()

        assert service.lookup_calls == [{"keyword": "김영수", "limit": 5}]
        assert page.selected_resident == {
            "member_id": 1,
            "display_name": "김*수",
            "birth_date": "1942-03-14",
            "room_no": "301",
            "visit_available": True,
            "guide_available": True,
        }
        assert page.resident_name_label.text() == "김*수 어르신"
        assert page.resident_birth_label.text() == "생년월일 1942-03-14"
        assert page.resident_room_label.text() == "호실 301호"
        assert "301호" in " ".join(_visible_texts(page))
        assert "어르신 정보를 확인했습니다" not in " ".join(_visible_texts(page))
        assert page.register_button.isEnabled() is True

        page.register_visit()

        assert service.register_calls == [
            {
                "visitor_name": "김민수",
                "phone_no": "010-1111-2222",
                "relationship": "아들",
                "visit_purpose": "가족 면회",
                "target_member_id": 1,
                "privacy_agreed": True,
                "kiosk_id": None,
            }
        ]
        assert page.visitor_session == {
            "visitor_id": 42,
            "member_id": 1,
            "resident_name": "김영수",
            "room_no": "301",
            "visit_status": "면회 가능",
        }
        assert routed_patients == [
            {
                "member_id": 1,
                "visitor_id": 42,
                "name": "김영수",
                "room": "301",
                "visit_status": "면회 가능",
                "guide_available": True,
            }
        ]
    finally:
        page.close()


def test_kiosk_visitor_registration_blocks_resident_lookup_until_visitor_context_ready():
    _app()

    from ui.kiosk_ui.main_window import KioskVisitorRegistrationPage

    class FakeKioskVisitorService:
        def lookup_residents(self, *, keyword, limit=10):
            raise AssertionError("resident lookup must wait for visitor fields and consent")

    page = KioskVisitorRegistrationPage(service=FakeKioskVisitorService())

    try:
        page.resident_search_input.setText("김영수")
        page.search_resident()

        assert page.search_button.isEnabled() is False
        assert page.selected_resident is None
        assert page.resident_name_label.text() == "방문자 정보 입력 필요"
        assert "방문자 정보와 개인정보 동의" in page.resident_birth_label.text()
    finally:
        page.close()


def test_kiosk_visitor_registration_shows_no_match_inline_without_status_popup():
    _app()

    from ui.kiosk_ui.main_window import KioskVisitorRegistrationPage

    class FakeKioskVisitorService:
        def lookup_residents(self, *, keyword, limit=10):
            return {
                "result_code": "NO_MATCH",
                "result_message": "일치하는 어르신 정보가 없습니다.",
                "reason_code": "RESIDENT_NOT_FOUND",
                "matches": [],
            }

    page = KioskVisitorRegistrationPage(service=FakeKioskVisitorService())

    try:
        page.visitor_name_input.setText("김민수")
        page.phone_input.setText("010-1111-2222")
        page.relationship_input.setText("아들")
        page.select_visit_purpose("family")
        page.privacy_checkbox.setChecked(True)
        page.resident_search_input.setText("999")
        page.search_resident()

        texts = " ".join(_visible_texts(page))
        assert page.findChild(QLabel, "kioskSearchStatusText") is None
        assert page.resident_name_label.text() == "검색 결과가 없습니다"
        assert page.resident_birth_label.text() == "이름 또는 호실을 다시 확인해 주세요."
        assert "일치하는 어르신 정보가 없습니다." not in texts
    finally:
        page.close()


def test_kiosk_visitor_registration_resident_name_label_reserves_font_height():
    app = _app()

    from ui.kiosk_ui.main_window import KioskVisitorRegistrationPage
    from ui.utils.core.styles import load_stylesheet

    app.setStyleSheet(load_stylesheet())
    page = KioskVisitorRegistrationPage()

    try:
        page.resize(1440, 960)
        page.show()
        page._show_resident_result(
            {
                "display_name": "김*수",
                "birth_date": "1942-03-14",
                "room_no": "301",
                "visit_available": True,
                "guide_available": True,
            }
        )
        app.processEvents()

        labels = [
            page.resident_name_label,
            page.resident_birth_label,
            page.resident_room_label,
            page.resident_visit_label,
        ]
        required_height = page.resident_name_label.fontMetrics().height() + 8
        assert page.resident_name_label.minimumHeight() >= required_height
        assert page.resident_name_label.geometry().height() >= required_height
        assert all(
            label.geometry().height() >= label.fontMetrics().height()
            for label in labels
        )
        for current_label, next_label in zip(labels, labels[1:]):
            current_bottom = current_label.geometry().y() + current_label.geometry().height()
            assert current_bottom <= next_label.geometry().y()
    finally:
        page.close()


def test_kiosk_guide_confirmation_ports_wireframe_layout_without_overlap():
    app = _app()

    from ui.kiosk_ui.main_window import KioskGuideConfirmationPage
    from ui.utils.core.styles import load_stylesheet

    app.setStyleSheet(load_stylesheet())
    page = KioskGuideConfirmationPage()

    try:
        page.resize(1440, 960)
        page.set_patient(
            {
                "member_id": 1,
                "visitor_id": 42,
                "name": "김*수",
                "room": "301",
                "visit_status": "면회 가능",
                "guide_available": True,
            }
        )
        page.show()
        app.processEvents()

        assert page.objectName() == "kioskGuideConfirmationPage"
        assert page.back_button.text() == ""
        assert page.home_button.text() == ""
        assert page.top_bar.height() == 96
        assert page.back_button.geometry().y() + page.back_button.geometry().height() < (
            page.top_bar.geometry().height()
        )
        assert page.home_button.geometry().y() + page.home_button.geometry().height() < (
            page.top_bar.geometry().height()
        )

        assert page.summary_card.width() <= 960
        assert page.robot_status_card.width() <= 960
        assert page.notice_card.width() <= 960
        assert page.summary_card.width() >= 860
        assert page.robot_status_card.width() >= 860
        assert page.notice_card.width() >= 860
        assert page.summary_title.text() == "김*수 어르신 (301호)"
        assert page.inline_status.isHidden() is True
        assert 80 <= page.confirm_button.height() <= 84
        assert 80 <= page.call_staff_button.height() <= 84

        assert page.notice_header.height() == 72
        assert page.notice_header_icon.objectName() == "kioskGuideNoticeHeaderIcon"
        assert page.notice_header_icon.width() == 44
        assert page.notice_header_icon.height() == 44
        assert len(page.notice_rows) == 3
        assert all(row.findChildren(QWidget, "kioskGuideNoticeLineIcon") for row in page.notice_rows)

        summary_bottom = page.summary_card.geometry().y() + page.summary_card.geometry().height()
        status_top = page.robot_status_card.geometry().y()
        status_bottom = status_top + page.robot_status_card.geometry().height()
        notice_top = page.notice_card.geometry().y()
        assert summary_bottom <= status_top
        assert status_bottom <= notice_top
    finally:
        page.close()


def test_kiosk_guide_confirmation_creates_db_backed_guide_task_before_command():
    _app()

    from ui.kiosk_ui.main_window import KioskGuideConfirmationPage

    class FakeGuideService:
        def __init__(self):
            self.created = []
            self.commands = []

        def create_guide_task(self, **kwargs):
            self.created.append(kwargs)
            return {
                "result_code": "ACCEPTED",
                "result_message": "안내 요청이 접수되었습니다.",
                "task_id": 3001,
                "task_status": "WAITING_DISPATCH",
                "phase": "WAIT_GUIDE_START_CONFIRM",
                "assigned_robot_id": "pinky1",
                "resident_name": "김*수",
                "room_no": "301",
                "destination_id": "delivery_room_301",
            }

        def send_guide_command(self, **kwargs):
            self.commands.append(kwargs)
            return True, "안내 제어 명령이 수락되었습니다.", {"accepted": True}

    progress_calls = []
    page = KioskGuideConfirmationPage(
        go_progress_page=lambda patient, session: progress_calls.append((patient, session))
    )
    page.service = FakeGuideService()

    try:
        page.set_patient(
            {
                "member_id": 1,
                "visitor_id": 42,
                "name": "김*수",
                "room": "301",
                "visit_status": "면회 가능",
                "guide_available": True,
            }
        )
        page.confirm_guidance()

        assert page.service.created[0]["visitor_id"] == 42
        assert page.service.created[0]["request_id"].startswith("kiosk_guide_")
        assert page.service.created[0]["idempotency_key"].startswith("idem_kiosk_guide_")
        assert page.service.commands == [
            {
                "task_id": 3001,
                "pinky_id": "pinky1",
                "command_type": "WAIT_TARGET_TRACKING",
            }
        ]
        assert progress_calls[0][1]["task_id"] == 3001
    finally:
        page.close()


def test_kiosk_progress_page_prefers_db_backed_guide_session_status():
    _app()

    from ui.kiosk_ui.main_window import KioskRobotGuidanceProgressPage

    class OfflineRuntimeService:
        def get_guide_runtime_status(self):
            raise RuntimeError("runtime unavailable")

    page = KioskRobotGuidanceProgressPage()
    page.service = OfflineRuntimeService()

    try:
        page.set_patient(
            {
                "member_id": 1,
                "visitor_id": 42,
                "name": "김*수",
                "room": "301",
                "visit_status": "면회 가능",
                "guide_available": True,
            },
            session={
                "task_id": 3001,
                "pinky_id": "pinky1",
                "task_status": "WAITING_DISPATCH",
                "phase": "WAIT_GUIDE_START_CONFIRM",
                "command_response": {
                    "task_status": "RUNNING",
                    "phase": "WAIT_TARGET_TRACKING",
                    "guide_phase": "WAIT_TARGET_TRACKING",
                },
            },
        )

        assert page.robot_state_chip.text() == "대상 확인 중"
        assert page.distance_label.text() == "로봇이 안내 대상을 확인하고 있습니다."
        assert "상태: 대상 확인 대기" in page.request_id_label.text()
    finally:
        page.close()


def test_kiosk_progress_page_starts_guidance_driving_with_detected_track():
    _app()

    from ui.kiosk_ui.main_window import KioskRobotGuidanceProgressPage

    class TrackingRuntimeService:
        def __init__(self):
            self.started = []

        def get_guide_runtime_status(self):
            return True, "tracking", {
                "guide_runtime": {
                    "last_update": {
                        "tracking_status": "TRACKING",
                        "active_track_id": "track_17",
                        "tracking_result_seq": 77,
                    }
                }
            }

        def start_guide_driving(self, **kwargs):
            self.started.append(kwargs)
            return True, "안내 주행을 시작했습니다.", {
                "result_code": "ACCEPTED",
                "task_id": kwargs["task_id"],
                "task_status": "RUNNING",
                "phase": "GUIDANCE_RUNNING",
                "target_track_id": kwargs["target_track_id"],
                "navigation_response": {"result_code": "ACCEPTED"},
            }

    service = TrackingRuntimeService()
    page = KioskRobotGuidanceProgressPage()
    page.service = service

    try:
        page.set_patient(
            {
                "member_id": 1,
                "visitor_id": 42,
                "name": "김*수",
                "room": "301",
                "visit_status": "면회 가능",
                "guide_available": True,
            },
            session={
                "task_id": 3001,
                "pinky_id": "pinky1",
                "task_status": "RUNNING",
                "phase": "WAIT_TARGET_TRACKING",
            },
        )

        assert page.start_driving_button.isEnabled() is True
        page.start_guidance_driving()

        assert service.started == [
            {
                "task_id": "3001",
                "pinky_id": "pinky1",
                "target_track_id": "track_17",
            }
        ]
        assert page.robot_state_chip.text() == "안내 중"
        assert page.distance_label.text() == "안내 주행을 시작했습니다."
    finally:
        page.close()


def test_kiosk_progress_page_uses_control_tracking_status_before_ros_runtime():
    _app()

    from ui.kiosk_ui.main_window import KioskRobotGuidanceProgressPage

    class ControlTrackingService:
        def __init__(self):
            self.task_status_calls = []
            self.status_calls = []
            self.runtime_called = False

        def get_task_status(self, *, task_id):
            self.task_status_calls.append(task_id)
            return {
                "result_code": "ACCEPTED",
                "task_id": int(task_id),
                "task_type": "GUIDE",
                "task_status": "RUNNING",
                "phase": "WAIT_TARGET_TRACKING",
                "assigned_robot_id": "pinky1",
            }

        def get_tracking_status(self, **kwargs):
            self.status_calls.append(kwargs)
            return True, "안내 대상을 확인했습니다.", {
                "tracking_status": "TRACKING",
                "active_track_id": "track_17",
                "target_track_id": "track_17",
                "tracking_result_seq": 881,
            }

        def get_guide_runtime_status(self):
            self.runtime_called = True
            raise RuntimeError("runtime should not be required")

    service = ControlTrackingService()
    page = KioskRobotGuidanceProgressPage()
    page.service = service

    try:
        page.set_patient(
            {
                "member_id": 1,
                "visitor_id": 42,
                "name": "김*수",
                "room": "301",
                "visit_status": "면회 가능",
                "guide_available": True,
            },
            session={
                "task_id": 3001,
                "pinky_id": "pinky1",
                "task_status": "RUNNING",
                "phase": "WAIT_TARGET_TRACKING",
            },
        )

        assert service.task_status_calls == ["3001"]
        assert service.status_calls == [{"task_id": "3001", "pinky_id": "pinky1"}]
        assert service.runtime_called is False
        assert page.detected_target_track_id == "track_17"
        assert page.start_driving_button.isEnabled() is True
        assert page.robot_state_chip.text() == "대상 확인 완료"
    finally:
        page.close()


def test_kiosk_progress_page_applies_task_status_query_to_guide_progress():
    _app()

    from ui.kiosk_ui.main_window import KioskRobotGuidanceProgressPage

    class GuideProgressService:
        def __init__(self):
            self.task_status_calls = []

        def get_task_status(self, *, task_id):
            self.task_status_calls.append(task_id)
            return {
                "result_code": "ACCEPTED",
                "task_id": int(task_id),
                "task_type": "GUIDE",
                "task_status": "RUNNING",
                "phase": "GUIDANCE_RUNNING",
                "assigned_robot_id": "pinky1",
            }

        def get_tracking_status(self, **_kwargs):
            return False, "대기 중", {"tracking_status": "NOT_TRACKING"}

        def get_guide_runtime_status(self):
            return False, "대기 중", {"guide_runtime": {"connected": False}}

    service = GuideProgressService()
    page = KioskRobotGuidanceProgressPage()
    page.service = service

    try:
        page.set_patient(
            {
                "member_id": 1,
                "visitor_id": 42,
                "name": "김*수",
                "room": "301",
                "visit_status": "면회 가능",
                "guide_available": True,
            },
            session={
                "task_id": 3001,
                "pinky_id": "pinky1",
                "task_status": "RUNNING",
                "phase": "WAIT_TARGET_TRACKING",
            },
        )

        assert service.task_status_calls == ["3001"]
        assert page.robot_state_chip.text() == "안내 중"
        assert page.distance_label.text() == "로봇을 따라 이동해주세요."
        assert page.start_driving_button.isEnabled() is False
        assert page.progress_stages[3].property("state") == "active"
        assert page.progress_stages[4].property("state") == "pending"
    finally:
        page.close()


def test_kiosk_staff_call_uses_in_app_modal_and_lobby_context():
    _app()

    from ui.kiosk_ui.main_window import KioskHomeWindow

    class FakeStaffCallService:
        def __init__(self):
            self.calls = []

        def submit_staff_call(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "result_code": "ACCEPTED",
                "result_message": "직원이 곧 도착합니다.",
                "reason_code": None,
                "call_id": "kiosk_call_77",
                "linked_visitor_id": None,
                "linked_member_id": None,
            }

    service = FakeStaffCallService()
    window = KioskHomeWindow(staff_call_service=service)

    try:
        window.show()
        window.home_page.call_card.clicked.emit()

        assert len(service.calls) == 1
        assert service.calls[0]["call_type"] == "직원 호출"
        assert service.calls[0]["visitor_id"] is None
        assert service.calls[0]["member_id"] is None
        assert service.calls[0]["kiosk_id"] == "lobby_kiosk_01"
        assert service.calls[0]["idempotency_key"].startswith("kiosk_staff_call_")

        assert window.staff_call_modal.isVisible() is True
        assert window.staff_call_modal.parent() is window.centralWidget()
        assert window.staff_call_modal.window() is window
        assert "직원 호출이 접수되었습니다." in _visible_texts(window.staff_call_modal)
        assert "직원이 곧 도착합니다." in _visible_texts(window.staff_call_modal)

        window.staff_call_modal.close_button.clicked.emit()
        assert window.staff_call_modal.isHidden() is True
    finally:
        window.close()


def test_kiosk_staff_call_includes_registered_visitor_context():
    _app()

    from ui.kiosk_ui.main_window import KioskHomeWindow

    class FakeStaffCallService:
        def __init__(self):
            self.calls = []

        def submit_staff_call(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "result_code": "ACCEPTED",
                "result_message": "직원이 곧 도착합니다.",
                "reason_code": None,
                "call_id": "member_event_9102",
                "linked_visitor_id": kwargs.get("visitor_id"),
                "linked_member_id": kwargs.get("member_id"),
            }

    service = FakeStaffCallService()
    patient = {
        "member_id": 1,
        "visitor_id": 42,
        "name": "김*수",
        "room": "301",
        "visit_status": "면회 가능",
        "guide_available": True,
    }
    window = KioskHomeWindow(staff_call_service=service)

    try:
        window.show()
        window._show_confirmation_page(patient)
        window.confirmation_page.call_staff_button.clicked.emit()
        window._show_progress_page(patient, session={"task_id": "guide_1"})
        window.progress_page.call_staff_button.clicked.emit()

        assert [call["visitor_id"] for call in service.calls] == [42, 42]
        assert [call["member_id"] for call in service.calls] == [1, 1]
        assert all(call["kiosk_id"] == "lobby_kiosk_01" for call in service.calls)
        assert "안내 화면" in service.calls[0]["description"]
        assert "안내 진행" in service.calls[1]["description"]
    finally:
        window.close()
