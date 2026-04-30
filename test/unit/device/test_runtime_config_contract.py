from pathlib import Path

import yaml

from test_support.paths import REPO_ROOT

DEVICE_ROOT = REPO_ROOT / "device"
MOBILE_SRC = DEVICE_ROOT / "ropi_mobile" / "src"
ARM_SRC = DEVICE_ROOT / "ropi_arm" / "src"

DELIVERY_ROOT = MOBILE_SRC / "ropi_delivery"
TRACKING_ROOT = MOBILE_SRC / "ropi_guide"
FALLEN_ROOT = MOBILE_SRC / "ropi_patrol"
JET_ARM_ROOT = ARM_SRC / "ropi_arm_control"


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
    assert "parameters=" in content


def test_ropi_delivery_runtime_config_contract():
    config_path = DELIVERY_ROOT / "config" / "pinky2" / "delivery.yaml"
    launch_path = DELIVERY_ROOT / "launch" / "ropi_delivery.launch.py"
    node_path = DELIVERY_ROOT / "ropi_delivery" / "mobile_controller_test.py"

    params = _load_ros_parameters(config_path, "pinky_amr_node")
    assert params["robot_id"] == "pinky2"
    assert params["action_name"] == "/ropi/control/pinky2/navigate_to_goal"
    assert params["status_topic"] == "/transport/amr_status"
    assert params["current_goal_topic"] == "/transport/current_goal"
    assert params["state_publish_period_sec"] == 0.5

    _assert_launch_uses_params_file(
        launch_path,
        package_name="ropi_delivery",
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
    launch_path = TRACKING_ROOT / "launch" / "guide.launch.py"
    node_path = TRACKING_ROOT / "ropi_guide" / "tracking_node.py"

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
        package_name="ropi_guide",
        config_subdir="tracking.yaml",
    )
    _assert_setup_installs(
        TRACKING_ROOT,
        "glob('launch/*.launch.py')",
        "glob('config/pinky1/*.yaml')",
    )
    launch_source = launch_path.read_text(encoding="utf-8")
    assert "executable='guide'" in launch_source or 'executable="guide"' in launch_source

    node_source = node_path.read_text(encoding="utf-8")
    assert '"192.168.4.15"' not in node_source
    assert "'192.168.4.15'" not in node_source


def test_fallen_detection_runtime_config_contract():
    config_path = FALLEN_ROOT / "config" / "pinky3" / "patrol.yaml"
    launch_path = FALLEN_ROOT / "launch" / "patrol.launch.py"
    client_node_path = FALLEN_ROOT / "ropi_patrol" / "fallen_detection_client.py"
    camera_node_path = FALLEN_ROOT / "ropi_patrol" / "ropi_camera.py"

    client_params = _load_ros_parameters(config_path, "fallen_detection_client")
    assert client_params["alarm_topic"] == "/fall_alarm"
    assert client_params["pinky_id"] == "pinky3"
    assert client_params["nav_check_interval_sec"] == 0.2
    assert len(client_params["waypoints"]) == 13
    assert all(isinstance(waypoint, str) for waypoint in client_params["waypoints"])

    camera_params = _load_ros_parameters(config_path, "ropi_camera")
    assert camera_params["server_ip"] == "192.168.0.89"
    assert camera_params["udp_port"] == 5005
    assert camera_params["stream_name"] == "pinky03_cam"
    assert camera_params["udp_packet_size"] == 1200
    assert camera_params["send_fps"] == 10.0
    assert camera_params["camera_width"] == 480
    assert camera_params["camera_height"] == 320
    assert camera_params["jpeg_quality"] == 70

    _assert_launch_uses_params_file(
        launch_path,
        package_name="ropi_patrol",
        config_subdir="patrol.yaml",
    )
    _assert_setup_installs(
        FALLEN_ROOT,
        "glob('launch/*.launch.py')",
        "glob('config/pinky3/*.yaml')",
        "fallen_detection_client = ropi_patrol.fallen_detection_client:main",
        "ropi_camera = ropi_patrol.ropi_camera:main",
    )

    client_source = client_node_path.read_text(encoding="utf-8")
    assert 'SERVER_IP = "' not in client_source
    assert "UDP_PORT =" not in client_source
    assert "TCP_PORT =" not in client_source
    assert '"192.168.0.89"' not in client_source
    assert "0.9576985239982605" not in client_source
    assert "self.declare_parameter(\"server_ip\"" not in client_source
    assert "self.declare_parameter(\"waypoints\"" in client_source

    camera_source = camera_node_path.read_text(encoding="utf-8")
    assert "self.declare_parameter(\"server_ip\"" in camera_source
    assert "self.declare_parameter(\"udp_port\"" in camera_source


def test_jet_arm_runtime_config_contract_is_kept():
    jetcobot1 = _load_ros_parameters(JET_ARM_ROOT / "config" / "jetcobot1" / "arm.yaml", "jet_arm_node")
    jetcobot2 = _load_ros_parameters(JET_ARM_ROOT / "config" / "jetcobot2" / "arm.yaml", "jet_arm_node")

    assert jetcobot1["arm_id"] == "arm1"
    assert jetcobot2["arm_id"] == "arm2"
    assert jetcobot1["port"] == "/dev/ttyJETCOBOT"
    assert jetcobot2["port"] == "/dev/ttyJETCOBOT"
    assert jetcobot1["baud"] == 1000000
    assert jetcobot2["baud"] == 1000000
