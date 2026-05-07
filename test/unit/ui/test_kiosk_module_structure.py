from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
KIOSK_MAIN_WINDOW = REPO_ROOT / "ui" / "kiosk_ui" / "main_window.py"
KIOSK_HOME_PAGE = REPO_ROOT / "ui" / "kiosk_ui" / "home_page.py"
KIOSK_REGISTRATION_PAGE = REPO_ROOT / "ui" / "kiosk_ui" / "registration_page.py"
KIOSK_SHARED_WIDGETS = REPO_ROOT / "ui" / "kiosk_ui" / "shared_widgets.py"


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


def test_kiosk_registration_page_is_split_from_main_window():
    from ui.kiosk_ui.main_window import KioskHomeWindow
    from ui.kiosk_ui.registration_page import (
        KioskPurposeOptionCard,
        KioskVisitorRegistrationPage,
    )
    from ui.kiosk_ui.shared_widgets import KioskResidentPersonIcon

    main_source = KIOSK_MAIN_WINDOW.read_text(encoding="utf-8")

    assert KioskHomeWindow.__name__ == "KioskHomeWindow"
    assert KioskVisitorRegistrationPage.__module__.endswith("registration_page")
    assert KioskPurposeOptionCard.__module__.endswith("registration_page")
    assert KioskResidentPersonIcon.__module__.endswith("shared_widgets")
    assert KIOSK_REGISTRATION_PAGE.exists()
    assert KIOSK_SHARED_WIDGETS.exists()
    assert "class KioskVisitorRegistrationPage" not in main_source
    assert "class KioskPurposeOptionCard" not in main_source
    assert "class KioskPurposeIcon" not in main_source
    assert "class KioskSearchIconButton" not in main_source
    assert "class KioskFooterNavigationButton" not in main_source
    assert "class KioskResidentPersonIcon" not in main_source
