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
        assert "어르신 찾기" in texts
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
        assert len(cards) == 3
        assert all(card.minimumHeight() >= 380 for card in cards)
        assert all(not card.findChildren(QPushButton) for card in cards)
        assert len(home.findChildren(QFrame, "kioskCardAccent")) == 0
        assert len(home.findChildren(QWidget, "kioskActionIconGlyph")) == 3
    finally:
        window.close()


def test_kiosk_resident_search_uses_if_gui_007_lookup_payload():
    _app()

    from ui.kiosk_ui.main_window import KioskResidentSearchPage

    class FakeKioskVisitorService:
        def __init__(self):
            self.calls = []

        def lookup_residents(self, *, keyword, limit=10):
            self.calls.append({"keyword": keyword, "limit": limit})
            return {
                "result_code": "FOUND",
                "result_message": "어르신 정보를 확인했습니다.",
                "reason_code": None,
                "matches": [
                    {
                        "member_id": 1,
                        "display_name": "김OO",
                        "room_no": "301",
                        "visit_available": True,
                        "guide_available": True,
                    }
                ],
            }

    service = FakeKioskVisitorService()
    page = KioskResidentSearchPage(service=service)

    try:
        page.search_input.setText(" 301 ")
        page.search_patient()

        assert service.calls == [{"keyword": "301", "limit": 5}]
        assert page.selected_patient == {
            "member_id": 1,
            "name": "김OO",
            "room": "301",
            "location": "호실 안내 가능",
            "status": "방문 등록 가능",
            "visit_available": True,
            "guide_available": True,
        }
        assert page.name_label.text() == "김OO 어르신"
        assert page.room_label.text() == "301호"
        assert page.location_label.text() == "위치: 호실 안내 가능"
        assert page.visit_label.text() == "면회 상태: 방문 등록 가능"
    finally:
        page.close()


def test_kiosk_resident_search_handles_no_match_from_if_gui_007():
    _app()

    from ui.kiosk_ui.main_window import KioskResidentSearchPage

    class FakeKioskVisitorService:
        def lookup_residents(self, *, keyword, limit=10):
            return {
                "result_code": "NO_MATCH",
                "result_message": "일치하는 어르신 정보가 없습니다.",
                "reason_code": "RESIDENT_NOT_FOUND",
                "matches": [],
            }

    page = KioskResidentSearchPage(service=FakeKioskVisitorService())

    try:
        page.search_input.setText("999")
        page.search_patient()

        assert page.selected_patient is None
        assert page.name_label.text() == "검색 결과가 없습니다"
        assert page.status_label.text() == "일치하는 어르신 정보가 없습니다."
    finally:
        page.close()
