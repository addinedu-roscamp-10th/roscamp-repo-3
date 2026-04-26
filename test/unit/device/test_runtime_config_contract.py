from pathlib import Path

import yaml

from test_support.paths import REPO_ROOT

DEVICE_ROOT = REPO_ROOT / "device"
MOBILE_SRC = DEVICE_ROOT / "ropi_mobile" / "src"
ARM_SRC = DEVICE_ROOT / "ropi_arm" / "src"

DELIVERY_ROOT = MOBILE_SRC / "pinky_delivery"
TRACKING_ROOT = MOBILE_SRC / "tracking"
FALLEN_ROOT = MOBILE_SRC / "fallen_detection"
JET_ARM_ROOT = ARM_SRC / "jet_arm_control"


def _load_ros_parameters(config_path: Path, node_name: str) -> dict:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert node_name in data
    assert "ros__parameters" in data[node_name]
    return data[node_name]["ros__parameters"]


def _assert_setup_installs(package_root: Path, *expected_fragments: str):
    setup_py = (package_root / "setup.py").read_text(encoding="utf-8")
    for fragment in expected_fragments:
        assert fragment in setup_py


def _assert_launch_uses_params_file(launch_path: Path, *, package_name: str, config_subdir: str):
    content = launch_path.read_text(encoding="utf-8")
    assert "DeclareLaunchArgument" in content
    assert "params_file" in content
    assert f'FindPackageShare("{package_name}")' in content or f"FindPackageShare('{package_name}')" in content
    assert f'"config", robot_id, "{config_subdir}"' in content or f"'config', robot_id, '{config_subdir}'" in content
    assert "parameters=[params_file]" in content


def test_pinky_delivery_runtime_config_contract():
    config_path = DELIVERY_ROOT / "config" / "pinky2" / "delivery.yaml"
    launch_path = DELIVERY_ROOT / "launch" / "pinky_delivery.launch.py"
    node_path = DELIVERY_ROOT / "pinky_delivery" / "mobile_controller_test.py"

    params = _load_ros_parameters(config_path, "pinky_amr_node")
    assert params["robot_id"] == "pinky2"
    assert params["action_name"] == "/ropi/control/pinky2/navigate_to_goal"
    assert params["status_topic"] == "/transport/amr_status"
    assert params["current_goal_topic"] == "/transport/current_goal"
    assert params["state_publish_period_sec"] == 0.5

    _assert_launch_uses_params_file(
        launch_path,
        package_name="pinky_delivery",
        config_subdir="delivery.yaml",
    )
    _assert_setup_installs(
        DELIVERY_ROOT,
        "glob('launch/*.launch.py')",
        "glob('config/pinky2/*.yaml')",
    )

    node_source = node_path.read_text(encoding="utf-8")
    assert 'declare_parameter("robot_id", "pinky2")' in node_source
    assert 'declare_parameter("action_name", "")' in node_source
    assert '"/ropi/control/pinky2/navigate_to_goal"' not in node_source


def test_tracking_runtime_config_contract():
    config_path = TRACKING_ROOT / "config" / "pinky1" / "tracking.yaml"
    launch_path = TRACKING_ROOT / "launch" / "tracking.launch.py"
    node_path = TRACKING_ROOT / "tracking" / "tracking_node.py"

    params = _load_ros_parameters(config_path, "tracking_node")
    assert params["server_ip"] == "192.168.4.15"
    assert params["server_video_port"] == 5005
    assert params["result_port"] == 6006
    assert params["detection_topic"] == "tracking"
    assert params["cmd_vel_topic"] == "/cmd_vel"
    assert params["cam_width"] == 320
    assert params["cam_height"] == 240

    _assert_launch_uses_params_file(
        launch_path,
        package_name="tracking",
        config_subdir="tracking.yaml",
    )
    _assert_setup_installs(
        TRACKING_ROOT,
        "glob('launch/*.launch.py')",
        "glob('config/pinky1/*.yaml')",
    )
    launch_source = launch_path.read_text(encoding="utf-8")
    assert "executable='tracking'" in launch_source or 'executable="tracking"' in launch_source

    node_source = node_path.read_text(encoding="utf-8")
    assert '"192.168.4.15"' not in node_source
    assert "'192.168.4.15'" not in node_source


def test_fallen_detection_runtime_config_contract():
    config_path = FALLEN_ROOT / "config" / "pinky3" / "patrol.yaml"
    launch_path = FALLEN_ROOT / "launch" / "patrol.launch.py"
    node_path = FALLEN_ROOT / "fallen_detection" / "fallen_detection_client_tcp.py"

    params = _load_ros_parameters(config_path, "fallen_detection_client_tcp")
    assert params["server_ip"] == "192.168.0.89"
    assert params["udp_port"] == 5005
    assert params["tcp_port"] == 6000
    assert params["alarm_topic"] == "/fall_alarm"
    assert params["send_fps"] == 10.0
    assert params["nav_check_interval_sec"] == 0.2
    assert params["camera_width"] == 320
    assert params["camera_height"] == 240
    assert params["jpeg_quality"] == 70
    assert len(params["waypoints"]) == 6
    assert all(isinstance(waypoint, str) for waypoint in params["waypoints"])

    _assert_launch_uses_params_file(
        launch_path,
        package_name="fallen_detection",
        config_subdir="patrol.yaml",
    )
    _assert_setup_installs(
        FALLEN_ROOT,
        "glob('launch/*.launch.py')",
        "glob('config/pinky3/*.yaml')",
    )

    node_source = node_path.read_text(encoding="utf-8")
    assert 'SERVER_IP = "' not in node_source
    assert "UDP_PORT =" not in node_source
    assert "TCP_PORT =" not in node_source
    assert '"192.168.0.89"' not in node_source
    assert "0.9576985239982605" not in node_source
    assert "self.declare_parameter(\"server_ip\"" in node_source
    assert "self.declare_parameter(\"waypoints\"" in node_source


def test_jet_arm_runtime_config_contract_is_kept():
    jetcobot1 = _load_ros_parameters(JET_ARM_ROOT / "config" / "jetcobot1" / "arm.yaml", "jet_arm_node")
    jetcobot2 = _load_ros_parameters(JET_ARM_ROOT / "config" / "jetcobot2" / "arm.yaml", "jet_arm_node")

    assert jetcobot1["arm_id"] == "arm1"
    assert jetcobot2["arm_id"] == "arm2"
    assert jetcobot1["port"] == "/dev/ttyJETCOBOT"
    assert jetcobot2["port"] == "/dev/ttyJETCOBOT"
    assert jetcobot1["baud"] == 1000000
    assert jetcobot2["baud"] == 1000000
