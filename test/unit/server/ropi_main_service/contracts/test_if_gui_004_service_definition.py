from test_support.paths import REPO_ROOT


ROPI_INTERFACE_ROOT = REPO_ROOT / "device" / "ropi_common" / "src" / "ropi_interface"
SRV_FILE = ROPI_INTERFACE_ROOT / "srv" / "GuideCommand.srv"
CMAKE_FILE = ROPI_INTERFACE_ROOT / "CMakeLists.txt"


def test_if_gui_004_guide_command_service_exists_with_spec_fields():
    assert SRV_FILE.exists(), "IF-GUI-004 GuideCommand service 파일이 아직 없습니다."

    content = SRV_FILE.read_text(encoding="utf-8")
    sections = [section.strip() for section in content.split("---")]

    assert "string task_id" in sections[0]
    assert "string command_type" in sections[0]
    assert "string target_track_id" in sections[0]
    assert "int32 wait_timeout_sec" in sections[0]
    assert "string finish_reason" in sections[0]
    assert "bool accepted" in sections[1]
    assert "string reason_code" in sections[1]
    assert "string message" in sections[1]


def test_if_gui_004_guide_command_service_is_registered_in_cmake():
    content = CMAKE_FILE.read_text(encoding="utf-8")

    assert '"srv/GuideCommand.srv"' in content
