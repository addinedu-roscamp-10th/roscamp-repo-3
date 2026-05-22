from dataclasses import dataclass


@dataclass(frozen=True)
class FmsRobotLaunchContract:
    robot_id: str
    map_id: str
    map_frame: str
    odom_frame: str
    base_frame: str
    lidar_frame: str
    cmd_vel_topic: str
    odom_topic: str
    scan_topic: str
    tf_topic: str
    tf_static_topic: str
    navigate_to_pose_action: str


def normalize_robot_id(robot_id: str) -> str:
    if not robot_id or robot_id.strip() != robot_id:
        raise ValueError("robot_id must be a non-empty namespace segment")
    if robot_id.startswith("/") or robot_id.endswith("/") or "/" in robot_id:
        raise ValueError("robot_id must be a relative namespace segment")
    return robot_id


def namespaced_name(robot_id: str, name: str) -> str:
    normalized_robot_id = normalize_robot_id(robot_id)
    normalized_name = name.strip("/")
    if not normalized_name:
        raise ValueError("name must be a non-empty ROS graph name segment")
    return f"/{normalized_robot_id}/{normalized_name}"


def build_fms_robot_contract(robot_id: str) -> FmsRobotLaunchContract:
    normalized_robot_id = normalize_robot_id(robot_id)

    return FmsRobotLaunchContract(
        robot_id=normalized_robot_id,
        map_id="map_0504",
        map_frame="map",
        odom_frame="odom",
        base_frame="base_footprint",
        lidar_frame="rplidar_link",
        cmd_vel_topic=namespaced_name(normalized_robot_id, "cmd_vel"),
        odom_topic=namespaced_name(normalized_robot_id, "odom"),
        scan_topic=namespaced_name(normalized_robot_id, "scan"),
        tf_topic=namespaced_name(normalized_robot_id, "tf"),
        tf_static_topic=namespaced_name(normalized_robot_id, "tf_static"),
        navigate_to_pose_action=namespaced_name(
            normalized_robot_id,
            "navigate_to_pose",
        ),
    )
