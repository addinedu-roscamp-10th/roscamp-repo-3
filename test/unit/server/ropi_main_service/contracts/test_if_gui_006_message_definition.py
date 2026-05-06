from test_support.paths import REPO_ROOT


ROPI_INTERFACE_ROOT = REPO_ROOT / "device" / "ropi_common" / "src" / "ropi_interface"
MESSAGE_FILE = ROPI_INTERFACE_ROOT / "msg" / "GuideTrackingUpdate.msg"
CMAKE_FILE = ROPI_INTERFACE_ROOT / "CMakeLists.txt"
PACKAGE_FILE = ROPI_INTERFACE_ROOT / "package.xml"


def test_if_gui_006_message_file_exists_with_spec_fields():
    assert MESSAGE_FILE.exists(), "IF-GUI-006 message 파일이 아직 없습니다."

    content = MESSAGE_FILE.read_text(encoding="utf-8")

    assert "string task_id" in content
    assert "string target_track_id" in content
    assert "string tracking_status" in content
    assert "uint32 tracking_result_seq" in content
    assert "builtin_interfaces/Time frame_ts" in content
    assert "bool bbox_valid" in content
    assert "int32[4] bbox_xyxy" in content
    assert "uint32 image_width_px" in content
    assert "uint32 image_height_px" in content


def test_if_gui_006_message_is_registered_in_ropi_interface_cmake():
    content = CMAKE_FILE.read_text(encoding="utf-8")

    assert '"msg/GuideTrackingUpdate.msg"' in content
    assert "DEPENDENCIES builtin_interfaces action_msgs geometry_msgs nav_msgs" in content


def test_if_gui_006_message_dependencies_are_declared_in_package_xml():
    content = PACKAGE_FILE.read_text(encoding="utf-8")

    assert "<depend>builtin_interfaces</depend>" in content
