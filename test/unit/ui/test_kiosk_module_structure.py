from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
KIOSK_MAIN_WINDOW = REPO_ROOT / "ui" / "kiosk_ui" / "main_window.py"
KIOSK_HOME_PAGE = REPO_ROOT / "ui" / "kiosk_ui" / "home_page.py"


def test_kiosk_home_page_is_split_from_main_window():
    from ui.kiosk_ui.home_page import KioskHomeActionCard, KioskHomePage
    from ui.kiosk_ui.main_window import KioskHomeWindow

    main_source = KIOSK_MAIN_WINDOW.read_text(encoding="utf-8")

    assert KioskHomeWindow.__name__ == "KioskHomeWindow"
    assert KioskHomePage.__module__.endswith("home_page")
    assert KioskHomeActionCard.__module__.endswith("home_page")
    assert KIOSK_HOME_PAGE.exists()
    assert "class KioskHomePage" not in main_source
    assert "class KioskHomeActionCard" not in main_source
    assert "class KioskActionIconGlyph" not in main_source
    assert "class KioskFooterStat" not in main_source
