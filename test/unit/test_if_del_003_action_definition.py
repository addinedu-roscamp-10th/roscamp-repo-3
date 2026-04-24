from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROPI_INTERFACE_ROOT = REPO_ROOT / "device" / "ropi_mobile" / "pinky_pro" / "src" / "ropi_interface"
ACTION_FILE = ROPI_INTERFACE_ROOT / "action" / "ArmManipulation.action"
CMAKE_FILE = ROPI_INTERFACE_ROOT / "CMakeLists.txt"
PACKAGE_FILE = ROPI_INTERFACE_ROOT / "package.xml"


def test_if_del_003_action_file_exists_with_spec_fields():
    assert ACTION_FILE.exists(), "IF-DEL-003 action 파일이 아직 없습니다."

    content = ACTION_FILE.read_text(encoding="utf-8")
    sections = [section.strip() for section in content.split("---")]

    assert "string task_id" in content
    assert "string transfer_direction" in content
    assert "string item_id" in content
    assert "uint32 quantity" in content
    assert "string robot_slot_id" in content
    assert "---" in content
    assert "uint32 processed_quantity" in content
    assert "string result_code" in content
    assert "string result_message" in content
    assert len(sections) == 3
    assert "string task_id" in sections[0]
    assert "string result_code" in sections[1]
    assert "uint32 processed_quantity" in sections[2]

def test_if_del_003_action_is_registered_in_ropi_interface_cmake():
    content = CMAKE_FILE.read_text(encoding="utf-8")

    assert '"action/ArmManipulation.action"' in content or '"ArmManipulation.action"' in content


def test_if_del_003_action_dependencies_are_declared_in_package_xml():
    content = PACKAGE_FILE.read_text(encoding="utf-8")

    assert "<depend>action_msgs</depend>" in content
