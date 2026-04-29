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
    assert "QFrame#systemStatusStrip" in qss
    assert "QLabel#systemStatusOnline" in qss
    assert "QLabel#systemStatusWarning" in qss
    assert "QLabel#systemStatusError" in qss
    assert "min-width: 260px" in qss
    assert "max-width: 260px" in qss


def test_main_qss_has_single_app_root_rule():
    qss = _stylesheet()

    assert qss.count("QWidget#appRoot") == 1
