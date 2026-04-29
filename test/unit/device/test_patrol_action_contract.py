from pathlib import Path

from test_support.paths import REPO_ROOT


INTERFACE_ROOT = REPO_ROOT / "device" / "ropi_common" / "src" / "ropi_interface"
PATROL_ROOT = REPO_ROOT / "device" / "ropi_mobile" / "src" / "ropi_patrol"


def test_execute_patrol_path_action_matches_if_pat_003_contract():
    action_path = INTERFACE_ROOT / "action" / "ExecutePatrolPath.action"
    content = action_path.read_text(encoding="utf-8")

    assert "string task_id" in content
    assert "nav_msgs/Path path" in content
    assert "int32 timeout_sec" in content
    assert "string result_code" in content
    assert "uint32 completed_waypoint_count" in content
    assert "string patrol_status" in content
    assert "uint32 current_waypoint_index" in content
    assert "geometry_msgs/PoseStamped current_pose" in content

    cmake = (INTERFACE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    package_xml = (INTERFACE_ROOT / "package.xml").read_text(encoding="utf-8")

    assert "find_package(nav_msgs REQUIRED)" in cmake
    assert '"action/ExecutePatrolPath.action"' in cmake
    assert "nav_msgs" in cmake
    assert "<depend>nav_msgs</depend>" in package_xml

    action_server = (PATROL_ROOT / "ropi_patrol" / "patrol_path_action_server.py").read_text(
        encoding="utf-8"
    )
    assert 'result.result_code = "SUCCEEDED"' in action_server
    assert 'result.result_code = "SUCCESS"' not in action_server


def test_fall_response_control_service_matches_if_pat_004_contract():
    srv_path = INTERFACE_ROOT / "srv" / "FallResponseControl.srv"
    content = srv_path.read_text(encoding="utf-8")

    assert "string task_id" in content
    assert "string command_type" in content
    assert "---" in content
    assert "bool accepted" in content
    assert "string message" in content

    cmake = (INTERFACE_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    package_xml = (PATROL_ROOT / "package.xml").read_text(encoding="utf-8")
    action_server = (PATROL_ROOT / "ropi_patrol" / "patrol_path_action_server.py").read_text(
        encoding="utf-8"
    )
    config = (PATROL_ROOT / "config" / "pinky3" / "patrol.yaml").read_text(
        encoding="utf-8"
    )

    assert '"srv/FallResponseControl.srv"' in cmake
    assert "<depend>std_msgs</depend>" in package_xml
    assert "from ropi_interface.srv import FallResponseControl" in action_server
    assert "START_FALL_ALERT" in action_server
    assert "CLEAR_AND_RESTART" in action_server
    assert "CLEAR_AND_STOP" in action_server
    assert 'fall_response_service_name: "/ropi/control/pinky3/fall_response_control"' in config


def test_ropi_patrol_launch_exposes_control_managed_patrol_action_server():
    setup_py = (PATROL_ROOT / "setup.py").read_text(encoding="utf-8")
    launch_py = (PATROL_ROOT / "launch" / "patrol.launch.py").read_text(encoding="utf-8")
    package_xml = (PATROL_ROOT / "package.xml").read_text(encoding="utf-8")
    config = (PATROL_ROOT / "config" / "pinky3" / "patrol.yaml").read_text(
        encoding="utf-8"
    )

    assert "<depend>ropi_interface</depend>" in package_xml
    assert "patrol_path_action_server = ropi_patrol.patrol_path_action_server:main" in setup_py
    assert 'executable="patrol_path_action_server"' in launch_py
    assert "patrol_path_action_server:" in config
    assert 'action_name: "/ropi/control/pinky3/execute_patrol_path"' in config
    assert "auto_start_patrol: false" in config
