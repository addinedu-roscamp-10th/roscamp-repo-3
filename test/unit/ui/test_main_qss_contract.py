from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
QSS_PATH = ROOT / "ui" / "utils" / "styles" / "main.qss"


def _stylesheet() -> str:
    return QSS_PATH.read_text(encoding="utf-8")


def test_main_qss_uses_ropi_admin_design_tokens():
    qss = _stylesheet()

    assert "#005C55" in qss
    assert "#004C46" in qss
    assert "#F5F7FA" in qss
    assert '"Pretendard", "Noto Sans KR", sans-serif' in qss
    assert "#4a6fdc" not in qss
    assert "#3558be" not in qss


def test_main_qss_defines_shared_admin_shell_components():
    qss = _stylesheet()

    assert "QFrame#adminSidebar" in qss
    assert "QFrame#pageHeader" in qss
    assert "QFrame#pageTimeCard" in qss
    assert "QLabel#timeCardClock" in qss
    assert "QLabel#timeCardDate" in qss
    assert "QLabel#pageHeaderEyebrow" not in qss
    assert "QFrame#systemStatusStrip" in qss
    assert "QLabel#systemStatusOnline" in qss
    assert "QLabel#systemStatusWarning" in qss
    assert "QLabel#systemStatusError" in qss
    assert "min-width: 260px" in qss
    assert "max-width: 260px" in qss


def test_main_qss_defines_task_request_page_components():
    qss = _stylesheet()

    assert "QPushButton#scenarioTabButton" in qss
    assert "QPushButton#scenarioTabButton:checked" in qss
    assert "QFrame#formFieldGroup" in qss
    assert "QFrame#formHost" in qss
    assert "QScrollArea#requestFormScroll" in qss
    assert "QFrame#prioritySegment" in qss
    assert "QPushButton#prioritySegmentButton" in qss
    assert "QPushButton#prioritySegmentButton:checked" in qss
    assert "QFrame#requestPreviewCard" in qss
    assert "QFrame#requestPreviewCard {\n    background: #004C46" not in qss
    assert "QFrame#robotStatusCard" in qss
    assert "QFrame#robotMapPlaceholder" in qss
    assert "QFrame#sideMetricRow" in qss
    assert "QLabel#sideMetricLabel" in qss
    assert "QLabel#sideMetricValue" in qss
    assert "QFrame#keyValueRow" in qss
    assert "QLabel#keyValueKey" in qss
    assert "QLabel#keyValueValue" in qss
    assert "QLabel#priorityChip" in qss
    assert "QLabel#robotStateChip" in qss
    assert "QFrame#resultPanel" in qss
    assert "QFrame#taskResultPanel" in qss
    assert "QFrame#taskResultPanelWarning" in qss
    assert "QLabel#previewValue" in qss
    assert "QLabel#resultMessage" in qss


def test_main_qss_defines_home_dashboard_components():
    qss = _stylesheet()

    assert "QFrame#homeTimeCard" in qss
    assert "QFrame#homeKpiCard" in qss
    assert "QFrame#homeKpiAccent" in qss
    assert "QFrame#homeRobotCard" in qss
    assert "QLabel#homeRobotFieldKey" in qss
    assert "QLabel#homeTaskFieldKey" in qss


def test_main_qss_defines_kiosk_ui_components():
    qss = _stylesheet()

    required_selectors = [
        "QWidget#kioskRoot",
        "QFrame#kioskTopBar",
        "QFrame#kioskHomeCanvas",
        "QLabel#kioskBrandIcon",
        "QLabel#kioskBrandTitle",
        "QLabel#kioskHeroTitle",
        "QFrame#kioskActionCard",
        "QFrame#kioskActionCardBody",
        "QFrame#kioskActionCard[accent=\"blue\"]",
        "QFrame#kioskIconBubble",
        "QPushButton#kioskGhostButton",
        "QFrame#kioskFooterBar",
        "QFrame#kioskFooterStat",
        "QWidget#kioskVisitorRegistrationPage",
        "QWidget#kioskGuideConfirmationPage",
        "QFrame#kioskRegistrationCanvas",
        "QFrame#kioskRegistrationFormCard",
        "QFrame#kioskRegistrationResidentCard",
        "QFrame#kioskPurposeOptionCard",
        "QFrame#kioskPurposeOptionCard[selected=\"true\"]",
        "QFrame#kioskPurposeIconBubble",
        "QLabel#kioskPurposeLabel",
        "QCheckBox#kioskPrivacyCheckbox",
        "QFrame#kioskSearchInputCard",
        "QLineEdit#kioskSearchInput",
        "QPushButton#kioskSearchSubmitButton",
        "QWidget#kioskResidentPersonIcon",
        "QLabel#kioskResidentRoom",
        "QFrame#kioskSearchBottomBar",
        "QPushButton#kioskTopIconButton",
        "QFrame#kioskConfirmationSummaryCard",
        "QFrame#kioskConfirmationPersonBubble",
        "QLabel#kioskReadyChip",
        "QFrame#kioskGuideNoticeCard",
        "QWidget#kioskGuideNoticeHeaderIcon",
        "QWidget#kioskGuideNoticeLineIcon",
        "QFrame#kioskGuideNoticeRow",
        "QPushButton#kioskConfirmationPrimaryButton",
        "QWidget#kioskStaffCallModalOverlay",
        "QFrame#kioskStaffCallModalCard",
        "QLabel#kioskStaffCallModalTitle",
        "QPushButton#kioskStaffCallModalCloseButton",
        "QFrame#kioskProgressCard",
        "QFrame#kioskRobotInfoCard",
        "QLabel#kioskRobotStateChip",
        "QFrame#kioskRobotProgressFill",
        "QFrame#kioskSafetyNotice",
    ]

    for selector in required_selectors:
        assert selector in qss
    assert "border-top: 12px solid" not in qss
    assert "QFrame#kioskCardAccent" not in qss
    assert "QWidget#kioskVisitorRegistrationPage {\n    background: #FFF8EE" in qss
    assert "QFrame#kioskRegistrationCanvas" in qss
    assert "qlineargradient" in qss
    assert "QFrame#kioskRegistrationTopBar" in qss
    assert "QPushButton#kioskSearchFooterButton {\n    min-height: 72px" in qss
    assert "QLineEdit#kioskRegistrationInput" in qss
    assert "min-height: 72px" in qss
    assert "max-height: 72px" in qss
    assert "padding: 0 18px" in qss
    assert "check.svg" in qss


def test_main_qss_overrides_native_input_subcontrols():
    qss = _stylesheet()

    assert "QComboBox::drop-down" in qss
    assert "QComboBox::down-arrow" in qss
    assert "QComboBox QAbstractItemView" in qss
    assert "QComboBox QLineEdit" in qss
    assert "QSpinBox::up-button" in qss
    assert "QSpinBox::down-button" in qss
    assert "QSpinBox::up-arrow" in qss
    assert "QSpinBox::down-arrow" in qss
    assert "__STYLE_ASSET_DIR__/chevron-down.svg" in qss
    assert "__STYLE_ASSET_DIR__/chevron-up.svg" in qss


def test_stylesheet_loader_resolves_asset_placeholder():
    from ui.utils.core.styles import load_stylesheet

    qss = load_stylesheet()

    assert "__STYLE_ASSET_DIR__" not in qss
    assert "chevron-down.svg" in qss
    assert "chevron-up.svg" in qss


def test_main_qss_has_single_app_root_rule():
    qss = _stylesheet()

    assert qss.count("QWidget#appRoot") == 1
