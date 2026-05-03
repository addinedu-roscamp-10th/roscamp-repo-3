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
        assert page.status_label.text() == ""
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
            "visit_available": True,
            "guide_available": True,
        }
        assert page.resident_name_label.text() == "김*수 어르신"
        assert page.resident_birth_label.text() == "생년월일 1942-03-14"
        assert "301" not in " ".join(_visible_texts(page))
        assert "어르신 정보를 확인했습니다" not in page.status_label.text()
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
        assert "방문자 정보와 개인정보 동의" in page.status_label.text()
    finally:
        page.close()
