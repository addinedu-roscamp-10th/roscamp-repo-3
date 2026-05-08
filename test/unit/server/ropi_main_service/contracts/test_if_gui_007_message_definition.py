from test_support.paths import REPO_ROOT


ROPI_INTERFACE_ROOT = REPO_ROOT / "device" / "ropi_common" / "src" / "ropi_interface"
MESSAGE_FILE = ROPI_INTERFACE_ROOT / "msg" / "GuidePhaseSnapshot.msg"
CMAKE_FILE = ROPI_INTERFACE_ROOT / "CMakeLists.txt"
PACKAGE_FILE = ROPI_INTERFACE_ROOT / "package.xml"


def test_if_gui_007_guide_phase_snapshot_message_exists_with_spec_fields():
    assert MESSAGE_FILE.exists(), "IF-GUI-007 GuidePhaseSnapshot message 파일이 아직 없습니다."

    content = MESSAGE_FILE.read_text(encoding="utf-8")

    assert "string task_id" in content
    assert "string pinky_id" in content
    assert "string guide_phase" in content
    assert "int32 target_track_id" in content
    assert "string reason_code" in content
    assert "uint32 seq" in content
    assert "builtin_interfaces/Time occurred_at" in content
    assert "confidence" not in content
    assert "tracking_available" not in content
    assert "bbox" not in content


def test_if_gui_007_guide_phase_snapshot_message_is_registered_in_cmake():
    content = CMAKE_FILE.read_text(encoding="utf-8")

    assert '"msg/GuidePhaseSnapshot.msg"' in content
    assert "DEPENDENCIES builtin_interfaces action_msgs geometry_msgs nav_msgs" in content


def test_if_gui_007_message_dependencies_are_declared_in_package_xml():
    content = PACKAGE_FILE.read_text(encoding="utf-8")

    assert "<depend>builtin_interfaces</depend>" in content
