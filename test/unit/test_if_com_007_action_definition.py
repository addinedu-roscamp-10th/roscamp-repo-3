from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROPI_INTERFACE_ROOT = REPO_ROOT / "device" / "ropi_mobile" / "pinky_pro" / "src" / "ropi_interface"
ACTION_FILE = ROPI_INTERFACE_ROOT / "action" / "NavigateToGoal.action"
CMAKE_FILE = ROPI_INTERFACE_ROOT / "CMakeLists.txt"
PACKAGE_FILE = ROPI_INTERFACE_ROOT / "package.xml"


def test_if_com_007_action_file_exists_with_spec_fields():
    assert ACTION_FILE.exists(), "IF-COM-007 action 파일이 아직 없습니다."

    content = ACTION_FILE.read_text(encoding="utf-8")
    sections = [section.strip() for section in content.split("---")]

    assert "string task_id" in content
    assert "string nav_phase" in content
    assert "geometry_msgs/PoseStamped goal_pose" in content
    assert "int32 timeout_sec" in content
    assert "---" in content
    assert "string nav_status" in content
    assert "geometry_msgs/PoseStamped current_pose" in content
    assert "float32 distance_remaining_m" in content
    assert "string result_code" in content
    assert "string result_message" in content
    assert "geometry_msgs/PoseStamped final_pose" in content
    assert "builtin_interfaces/Time finished_at" in content
    assert len(sections) == 3
    assert "string task_id" in sections[0]
    assert "string result_code" in sections[1]
    assert "string nav_status" in sections[2]

def test_if_com_007_action_is_registered_in_ropi_interface_cmake():
    content = CMAKE_FILE.read_text(encoding="utf-8")

    assert 'find_package(geometry_msgs REQUIRED)' in content
    assert '"action/NavigateToGoal.action"' in content or '"NavigateToGoal.action"' in content
    assert "DEPENDENCIES builtin_interfaces std_msgs action_msgs geometry_msgs" in content


def test_if_com_007_action_dependencies_are_declared_in_package_xml():
    content = PACKAGE_FILE.read_text(encoding="utf-8")

    assert "<depend>geometry_msgs</depend>" in content
