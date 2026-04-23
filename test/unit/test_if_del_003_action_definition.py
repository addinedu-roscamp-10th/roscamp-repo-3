from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PINKY_INTERFACES_ROOT = (
    REPO_ROOT / "device" / "ropi_mobile" / "pinky_pro" / "src" / "pinky_pro" / "pinky_interfaces"
)
ACTION_FILE = PINKY_INTERFACES_ROOT / "action" / "ExecuteManipulation.action"
CMAKE_FILE = PINKY_INTERFACES_ROOT / "CMakeLists.txt"
PACKAGE_FILE = PINKY_INTERFACES_ROOT / "package.xml"


def test_if_del_003_action_file_exists_with_spec_fields():
    assert ACTION_FILE.exists(), "IF-DEL-003 action 파일이 아직 없습니다."

    content = ACTION_FILE.read_text(encoding="utf-8")

    assert "string task_id" in content
    assert "string transfer_direction" in content
    assert "string item_id" in content
    assert "uint32 quantity" in content
    assert "string robot_slot_id" in content
    assert "---" in content
    assert "uint32 processed_quantity" in content
    assert "string result_code" in content
    assert "string result_message" in content


def test_if_del_003_action_is_registered_in_pinky_interfaces_cmake():
    content = CMAKE_FILE.read_text(encoding="utf-8")

    assert '"action/ExecuteManipulation.action"' in content or '"ExecuteManipulation.action"' in content


def test_if_del_003_action_dependencies_are_declared_in_package_xml():
    content = PACKAGE_FILE.read_text(encoding="utf-8")

    assert "<depend>action_msgs</depend>" in content
