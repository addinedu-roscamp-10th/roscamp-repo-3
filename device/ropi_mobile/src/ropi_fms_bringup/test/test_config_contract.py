from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_nav2_fms_params_use_relative_scan_and_base_footprint():
    params = (PACKAGE_ROOT / "config" / "nav2_params_fms.yaml").read_text()

    assert "robot_base_frame: base_link" not in params
    assert "robot_base_frame: base_footprint" in params
    assert "topic: /scan" not in params
    assert "topic: scan" in params
    assert "enable_stamped_cmd_vel: true" not in params
    assert "enable_stamped_cmd_vel: True" not in params
    assert params.count("enable_stamped_cmd_vel: false") >= 3


def test_fms_launch_avoids_vendor_nested_namespace_and_controller_yaml_root_rewrite():
    launch_source = (PACKAGE_ROOT / "launch" / "pinky_fms.launch.py").read_text()

    assert "bringup_launch.xml" not in launch_source
    assert "localization_launch.xml" in launch_source
    assert "navigation_launch.xml" in launch_source
    assert '"namespace": ""' in launch_source
    assert 'LaunchConfiguration("nav2_params_file")' in launch_source
    assert 'DeclareLaunchArgument("nav2_params_file"' in launch_source
    assert 'LaunchConfiguration("params_file")' not in launch_source
    assert "namespaced_localization_params = RewrittenYaml" in launch_source
    assert "namespaced_navigation_params = RewrittenYaml" in launch_source
    assert "root_key=robot_id" in launch_source
    assert '"params_file": namespaced_localization_params' in launch_source
    assert '"params_file": namespaced_navigation_params' in launch_source
    assert '"params_file": namespaced_nav2_params' not in launch_source


def test_fms_launch_uses_current_physical_pinky_driver_contract():
    launch_source = (PACKAGE_ROOT / "launch" / "pinky_fms.launch.py").read_text()

    assert 'package="pinky_bringup"' in launch_source
    assert 'executable="bringup"' in launch_source
    assert "controller_manager" not in launch_source
    assert "ros2_control_node" not in launch_source
    assert 'DeclareLaunchArgument("lidar_serial_port", default_value="/dev/ttyS0")' in launch_source
    assert '"serial_port": lidar_serial_port' in launch_source
