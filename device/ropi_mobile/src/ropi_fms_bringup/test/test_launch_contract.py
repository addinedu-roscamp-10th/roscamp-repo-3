import pytest

from ropi_fms_bringup.launch_contract import build_fms_robot_contract


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
