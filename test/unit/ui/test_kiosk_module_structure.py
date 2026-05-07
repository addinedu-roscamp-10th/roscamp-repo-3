from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
KIOSK_MAIN_WINDOW = REPO_ROOT / "ui" / "kiosk_ui" / "main_window.py"
KIOSK_HOME_PAGE = REPO_ROOT / "ui" / "kiosk_ui" / "home_page.py"
KIOSK_REGISTRATION_PAGE = REPO_ROOT / "ui" / "kiosk_ui" / "registration_page.py"
KIOSK_GUIDE_CONFIRMATION_PAGE = (
    REPO_ROOT / "ui" / "kiosk_ui" / "guide_confirmation_page.py"
)
KIOSK_GUIDE_PROGRESS_PAGE = REPO_ROOT / "ui" / "kiosk_ui" / "guide_progress_page.py"
KIOSK_STAFF_CALL_MODAL = REPO_ROOT / "ui" / "kiosk_ui" / "staff_call_modal.py"
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


def test_kiosk_guide_confirmation_page_is_split_from_main_window():
    from ui.kiosk_ui.guide_confirmation_page import (
        KioskConfirmationActionButton,
        KioskGuideConfirmationPage,
        KioskGuideNoticeGlyph,
        KioskTopIconButton,
    )
    from ui.kiosk_ui.main_window import KioskHomeWindow

    main_source = KIOSK_MAIN_WINDOW.read_text(encoding="utf-8")

    assert KioskHomeWindow.__name__ == "KioskHomeWindow"
    assert KioskGuideConfirmationPage.__module__.endswith("guide_confirmation_page")
    assert KioskTopIconButton.__module__.endswith("guide_confirmation_page")
    assert KioskGuideNoticeGlyph.__module__.endswith("guide_confirmation_page")
    assert KioskConfirmationActionButton.__module__.endswith(
        "guide_confirmation_page"
    )
    assert KIOSK_GUIDE_CONFIRMATION_PAGE.exists()
    assert "class KioskGuideConfirmationPage" not in main_source
    assert "class KioskTopIconButton" not in main_source
    assert "class KioskGuideNoticeGlyph" not in main_source
    assert "class KioskConfirmationActionButton" not in main_source


def test_kiosk_guide_progress_page_is_split_from_main_window():
    from ui.kiosk_ui.guide_progress_page import (
        KioskProgressStage,
        KioskRobotGuidanceProgressPage,
    )
    from ui.kiosk_ui.main_window import KioskHomeWindow

    main_source = KIOSK_MAIN_WINDOW.read_text(encoding="utf-8")

    assert KioskHomeWindow.__name__ == "KioskHomeWindow"
    assert KioskRobotGuidanceProgressPage.__module__.endswith("guide_progress_page")
    assert KioskProgressStage.__module__.endswith("guide_progress_page")
    assert KIOSK_GUIDE_PROGRESS_PAGE.exists()
    assert "class KioskRobotGuidanceProgressPage" not in main_source
    assert "class KioskProgressStage" not in main_source


def test_kiosk_staff_call_modal_is_split_from_main_window():
    from ui.kiosk_ui.main_window import KioskHomeWindow
    from ui.kiosk_ui.staff_call_modal import KioskStaffCallModal

    main_source = KIOSK_MAIN_WINDOW.read_text(encoding="utf-8")

    assert KioskHomeWindow.__name__ == "KioskHomeWindow"
    assert KioskStaffCallModal.__module__.endswith("staff_call_modal")
    assert KIOSK_STAFF_CALL_MODAL.exists()
    assert "class KioskStaffCallModal" not in main_source
