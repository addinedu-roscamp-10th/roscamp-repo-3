import copy
import os
import tempfile

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource


def _load_robot_specs(config_path):
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    robots = config.get("robots", [])
    if not robots:
        raise RuntimeError(f"No robots defined in config: {config_path}")

    return robots


def _write_nav2_params(base_params_path, robot):
    with open(base_params_path, "r", encoding="utf-8") as params_file:
        base_params = yaml.safe_load(params_file)

    params = copy.deepcopy(base_params)
    namespace = robot["namespace"]
    x = float(robot["x"])
    y = float(robot["y"])
    yaw = float(robot.get("yaw", 0.0))
    odom_frame = f"{namespace}/odom"
    base_footprint_frame = f"{namespace}/base_footprint"
    base_link_frame = f"{namespace}/base_link"

    amcl_params = params["amcl"]["ros__parameters"]
    amcl_params["base_frame_id"] = base_footprint_frame
    amcl_params["odom_frame_id"] = odom_frame
    amcl_params["scan_topic"] = "scan"
    amcl_params["initial_pose"] = {
        "x": x,
        "y": y,
        "z": 0.0,
        "yaw": yaw,
    }

    bt_params = params["bt_navigator"]["ros__parameters"]
    bt_params["robot_base_frame"] = base_link_frame
    bt_params["odom_topic"] = "odom"

    local_costmap_params = params["local_costmap"]["local_costmap"]["ros__parameters"]
    local_costmap_params["global_frame"] = odom_frame
    local_costmap_params["robot_base_frame"] = base_footprint_frame
    local_costmap_params["voxel_layer"]["scan"]["topic"] = "scan"

    global_costmap_params = params["global_costmap"]["global_costmap"]["ros__parameters"]
    global_costmap_params["robot_base_frame"] = base_footprint_frame
    global_costmap_params["obstacle_layer"]["scan"]["topic"] = "scan"

    behavior_params = params["behavior_server"]["ros__parameters"]
    behavior_params["local_frame"] = odom_frame
    behavior_params["robot_base_frame"] = base_footprint_frame

    velocity_smoother_params = params["velocity_smoother"]["ros__parameters"]
    velocity_smoother_params["odom_topic"] = "odom"

    nav2_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f"{namespace}_nav2_",
        suffix=".yaml",
        delete=False,
    )
    with nav2_file:
        yaml.safe_dump(params, nav2_file, sort_keys=False)

    return nav2_file.name


def _launch_fleet_nav2(context):
    robots_config = LaunchConfiguration("robots_config").perform(context)
    base_params = LaunchConfiguration("nav2_params").perform(context)
    map_path = LaunchConfiguration("map").perform(context)
    use_sim_time = LaunchConfiguration("use_sim_time").perform(context)
    autostart = LaunchConfiguration("autostart").perform(context)
    use_composition = LaunchConfiguration("use_composition").perform(context)
    use_respawn = LaunchConfiguration("use_respawn").perform(context)
    log_level = LaunchConfiguration("log_level").perform(context)

    robots = _load_robot_specs(robots_config)
    localization_launch = os.path.join(
        get_package_share_directory("pinky_navigation"),
        "launch",
        "localization_launch.xml",
    )
    navigation_launch = os.path.join(
        get_package_share_directory("pinky_navigation"),
        "launch",
        "navigation_launch.xml",
    )

    actions = [LogInfo(msg=f"Using map for Nav2: {map_path}")]

    for robot in robots:
        namespace = robot["namespace"]
        params_file = _write_nav2_params(base_params, robot)
        actions.append(
            LogInfo(
                msg=f"Launching Nav2 for {namespace} with params {params_file}"
            )
        )
        actions.append(
            IncludeLaunchDescription(
                XMLLaunchDescriptionSource(localization_launch),
                launch_arguments={
                    "namespace": namespace,
                    "map": map_path,
                    "params_file": params_file,
                    "use_sim_time": use_sim_time,
                    "autostart": autostart,
                    "container_name": f"{namespace}_nav2_container",
                    "use_composition": use_composition,
                    "use_respawn": use_respawn,
                    "log_level": log_level,
                }.items(),
            )
        )
        actions.append(
            IncludeLaunchDescription(
                XMLLaunchDescriptionSource(navigation_launch),
                launch_arguments={
                    "namespace": namespace,
                    "params_file": params_file,
                    "use_sim_time": use_sim_time,
                    "autostart": autostart,
                    "container_name": f"{namespace}_nav2_container",
                    "use_composition": use_composition,
                    "use_respawn": use_respawn,
                    "log_level": log_level,
                }.items(),
            )
        )

    return actions


def generate_launch_description():
    sim_launch = os.path.join(
        get_package_share_directory("pinky_fleet_sim"),
        "launch",
        "two_pinky_sim.launch.py",
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("world_name", default_value="fleet_practice_large.world"),
            DeclareLaunchArgument("gz_partition", default_value="pinky_fleet_sim"),
            DeclareLaunchArgument(
                "robots_config",
                default_value=os.path.join(
                    get_package_share_directory("pinky_fleet_sim"),
                    "config",
                    "two_pinky_robots.yaml",
                ),
            ),
            DeclareLaunchArgument(
                "map",
                default_value=os.path.join(
                    get_package_share_directory("pinky_fleet_sim"),
                    "maps",
                    "fleet_practice_large.yaml",
                ),
            ),
            DeclareLaunchArgument(
                "nav2_params",
                default_value=os.path.join(
                    get_package_share_directory("pinky_navigation"),
                    "params",
                    "nav2_params.yaml",
                ),
            ),
            DeclareLaunchArgument("use_sim_time", default_value="True"),
            DeclareLaunchArgument("autostart", default_value="True"),
            DeclareLaunchArgument("use_composition", default_value="False"),
            DeclareLaunchArgument("use_respawn", default_value="False"),
            DeclareLaunchArgument("log_level", default_value="info"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(sim_launch),
                launch_arguments={
                    "world_name": LaunchConfiguration("world_name"),
                    "gz_partition": LaunchConfiguration("gz_partition"),
                    "robots_config": LaunchConfiguration("robots_config"),
                }.items(),
            ),
            OpaqueFunction(function=_launch_fleet_nav2),
        ]
    )
