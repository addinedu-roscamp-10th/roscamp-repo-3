from pathlib import Path
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[2]
DEVICE_ROOT = REPO_ROOT / "device"
ROPI_INTERFACE_ROOT = DEVICE_ROOT / "ropi_common" / "src" / "ropi_interface"
PINKY_CONFIG_ROOT = DEVICE_ROOT / "ropi_mobile" / "src" / "ropi_pinky_config"
JET_ARM_ROOT = DEVICE_ROOT / "ropi_arm" / "src" / "jet_arm_control"


def test_ropi_interface_lives_in_common_device_workspace():
    assert ROPI_INTERFACE_ROOT.exists()
    assert (ROPI_INTERFACE_ROOT / "action" / "NavigateToGoal.action").exists()
    assert (ROPI_INTERFACE_ROOT / "action" / "ArmManipulation.action").exists()

    root = ET.fromstring((ROPI_INTERFACE_ROOT / "package.xml").read_text(encoding="utf-8"))
    assert root.findtext("name") == "ropi_interface"
    assert root.findtext("member_of_group") == "rosidl_interface_packages"


def test_pinky_manufacturer_workspace_is_not_tracked_in_repo():
    assert not (DEVICE_ROOT / "ropi_mobile" / "pinky_pro").exists()


def test_pinky_config_wraps_robot_specific_nav_files():
    assert (PINKY_CONFIG_ROOT / "launch" / "pinky_nav.launch.py").exists()

    for robot_id in ("pinky1", "pinky2", "pinky3"):
        assert (PINKY_CONFIG_ROOT / "config" / robot_id / "nav2_params.yaml").exists()
        assert (PINKY_CONFIG_ROOT / "config" / robot_id / "mapper_params.yaml").exists()
        assert (PINKY_CONFIG_ROOT / "maps" / robot_id / "map.yaml").exists()


def test_jet_arm_control_is_shared_between_jetcobots():
    setup_py = (JET_ARM_ROOT / "setup.py").read_text(encoding="utf-8")
    node_py = (JET_ARM_ROOT / "jet_arm_control" / "arm1_node.py").read_text(encoding="utf-8")

    assert "package_name = 'jet_arm_control'" in setup_py
    assert "jet_arm_node = jet_arm_control.arm1_node:main" in setup_py
    assert 'declare_parameter("arm_id", "arm1")' in node_py
    assert 'f"/ropi/arm/{self.arm_id}/execute_manipulation"' in node_py
