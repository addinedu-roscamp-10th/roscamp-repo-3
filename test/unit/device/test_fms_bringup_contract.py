import sys

import pytest
import yaml

from test_support.paths import REPO_ROOT


FMS_BRINGUP_ROOT = REPO_ROOT / "device" / "ropi_mobile" / "src" / "ropi_fms_bringup"
sys.path.insert(0, str(FMS_BRINGUP_ROOT))

from ropi_fms_bringup.launch_contract import build_fms_robot_contract  # noqa: E402


def load_nav2_params():
    return yaml.safe_load(
        (FMS_BRINGUP_ROOT / "config" / "nav2_params_fms.yaml").read_text(
            encoding="utf-8"
        )
    )


def test_nav2_fms_params_use_relative_scan_and_base_footprint():
    params = (FMS_BRINGUP_ROOT / "config" / "nav2_params_fms.yaml").read_text(
        encoding="utf-8"
    )
    nav2_params = load_nav2_params()

    assert "robot_base_frame: base_link" not in params
    assert "robot_base_frame: base_footprint" in params
    assert "topic: /scan" not in params
    assert "topic: scan" in params
    assert "enable_stamped_cmd_vel: true" not in params
    assert "enable_stamped_cmd_vel: True" not in params
    assert params.count("enable_stamped_cmd_vel: false") >= 3
    assert (
        nav2_params["local_costmap"]["local_costmap"]["ros__parameters"]["voxel_layer"][
            "scan"
        ]["topic"]
        == "scan"
    )
    assert (
        nav2_params["global_costmap"]["global_costmap"]["ros__parameters"][
            "obstacle_layer"
        ]["scan"]["topic"]
        == "scan"
    )


def test_nav2_fms_params_match_team_final_amcl_and_controller_tuning():
    params = load_nav2_params()

    amcl = params["amcl"]["ros__parameters"]
    assert amcl["update_min_a"] == 0.01
    assert amcl["update_min_d"] == 0.01
    assert amcl["z_hit"] == 0.75
    assert amcl["z_max"] == 0.0
    assert amcl["z_rand"] == 0.2
    assert amcl["initial_pose"] == [-0.004, 0.023, -0.010]

    controller = params["controller_server"]["ros__parameters"]
    assert controller["enable_stamped_cmd_vel"] is False
    assert controller["general_goal_checker"]["xy_goal_tolerance"] == 0.03
    assert controller["general_goal_checker"]["yaw_goal_tolerance"] == 0.08
    assert (
        controller["FollowPath"]["plugin"]
        == "nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController"
    )
    assert controller["FollowPath"]["desired_linear_vel"] == 0.15
    assert controller["FollowPath"]["rotate_to_heading_angular_vel"] == 1.0
    assert controller["FollowPath"]["use_final_rotation"] is True


def test_nav2_fms_params_match_team_final_costmap_and_smoother_tuning():
    params = load_nav2_params()

    local_costmap = params["local_costmap"]["local_costmap"]["ros__parameters"]
    assert local_costmap["width"] == 1
    assert local_costmap["height"] == 1
    assert local_costmap["resolution"] == 0.02
    assert (
        local_costmap["footprint"]
        == "[[0.057, 0.052], [0.057, -0.052], [-0.057, -0.052], [-0.057, 0.052]]"
    )
    assert local_costmap["inflation_layer"]["cost_scaling_factor"] == 3.5
    assert local_costmap["inflation_layer"]["inflation_radius"] == 0.05

    global_costmap = params["global_costmap"]["global_costmap"]["ros__parameters"]
    assert global_costmap["footprint_padding"] == 0.0
    assert global_costmap["resolution"] == 0.02
    assert global_costmap["inflation_layer"]["cost_scaling_factor"] == 10.0
    assert global_costmap["inflation_layer"]["inflation_radius"] == 0.15

    planner = params["planner_server"]["ros__parameters"]["GridBased"]
    assert planner["tolerance"] == 0.10
    assert planner["use_astar"] is True

    velocity_smoother = params["velocity_smoother"]["ros__parameters"]
    assert velocity_smoother["max_velocity"] == [0.25, 0.0, 1.5]
    assert velocity_smoother["min_velocity"] == [-0.25, 0.0, -1.5]


def test_fms_launch_avoids_vendor_nested_namespace_and_controller_yaml_root_rewrite():
    launch_source = (FMS_BRINGUP_ROOT / "launch" / "pinky_fms.launch.py").read_text(
        encoding="utf-8"
    )

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
    launch_source = (FMS_BRINGUP_ROOT / "launch" / "pinky_fms.launch.py").read_text(
        encoding="utf-8"
    )

    assert 'package="pinky_bringup"' in launch_source
    assert 'executable="bringup"' in launch_source
    assert "controller_manager" not in launch_source
    assert "ros2_control_node" not in launch_source
    assert (
        'DeclareLaunchArgument("lidar_serial_port", default_value="/dev/ttyS0")'
        in launch_source
    )
    assert '"serial_port": lidar_serial_port' in launch_source


@pytest.mark.parametrize("robot_id", ["pinky1", "pinky3"])
def test_fms_robot_contract_uses_map_0504_and_local_tf_frames(robot_id):
    contract = build_fms_robot_contract(robot_id)

    assert contract.robot_id == robot_id
    assert contract.map_id == "map_0504"
    assert contract.map_frame == "map"
    assert contract.odom_frame == "odom"
    assert contract.base_frame == "base_footprint"
    assert contract.lidar_frame == "rplidar_link"


@pytest.mark.parametrize("robot_id", ["pinky1", "pinky3"])
def test_fms_robot_contract_namespaces_collision_prone_ros_names(robot_id):
    contract = build_fms_robot_contract(robot_id)

    assert contract.cmd_vel_topic == f"/{robot_id}/cmd_vel"
    assert contract.odom_topic == f"/{robot_id}/odom"
    assert contract.scan_topic == f"/{robot_id}/scan"
    assert contract.tf_topic == f"/{robot_id}/tf"
    assert contract.tf_static_topic == f"/{robot_id}/tf_static"
    assert contract.navigate_to_pose_action == f"/{robot_id}/navigate_to_pose"


@pytest.mark.parametrize("robot_id", ["", "/", "pinky/1", "/pinky1"])
def test_fms_robot_contract_rejects_ambiguous_robot_ids(robot_id):
    with pytest.raises(ValueError):
        build_fms_robot_contract(robot_id)
