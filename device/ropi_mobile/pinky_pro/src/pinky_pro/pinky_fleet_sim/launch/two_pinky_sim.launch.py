import os
import signal
import tempfile
import time

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _cleanup_stale_gz_servers(context):
    world_path = LaunchConfiguration("world").perform(context)
    world_name = os.path.basename(world_path)
    stale_processes = []

    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue

        pid = int(entry.name)
        if pid == os.getpid():
            continue

        try:
            with open(f"/proc/{pid}/cmdline", "rb") as cmdline_file:
                cmdline = cmdline_file.read().replace(b"\x00", b" ").decode("utf-8", "ignore").strip()
        except OSError:
            continue

        if not cmdline:
            continue

        if world_path not in cmdline and world_name not in cmdline:
            continue

        if "gz sim" not in cmdline and "gz-sim-server" not in cmdline:
            continue

        stale_processes.append((pid, cmdline))

    if not stale_processes:
        return []

    original_processes = list(stale_processes)

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        remaining = []
        for pid, cmdline in stale_processes:
            try:
                os.kill(pid, 0)
            except OSError:
                continue

            remaining.append((pid, cmdline))
            try:
                os.kill(pid, sig)
            except OSError:
                pass

        stale_processes = remaining
        if not stale_processes:
            break

        deadline = time.time() + 2.0
        while time.time() < deadline and stale_processes:
            time.sleep(0.1)
            stale_processes = [
                (pid, cmdline)
                for pid, cmdline in stale_processes
                if os.path.exists(f"/proc/{pid}")
            ]

        if not stale_processes:
            break

    survivor_pids = {pid for pid, _ in stale_processes}
    killed_processes = [
        (pid, cmdline)
        for pid, cmdline in original_processes
        if pid not in survivor_pids
    ]

    messages = [
        LogInfo(msg=f"Killed stale Gazebo server pid={pid}: {cmdline}")
        for pid, cmdline in killed_processes
    ]

    messages.extend(
        LogInfo(msg=f"Failed to stop stale Gazebo server pid={pid}: {cmdline}")
        for pid, cmdline in stale_processes
    )

    return messages


def _load_robot_specs(config_path):
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}

    robots = config.get("robots", [])
    if not robots:
        raise RuntimeError(f"No robots defined in config: {config_path}")

    return robots


def _write_bridge_config(robots):
    bridges = [
        {
            "ros_topic_name": "clock",
            "gz_topic_name": "clock",
            "ros_type_name": "rosgraph_msgs/msg/Clock",
            "gz_type_name": "gz.msgs.Clock",
            "direction": "GZ_TO_ROS",
        }
    ]

    for robot in robots:
        namespace = robot["namespace"]
        gz_prefix = f"{namespace}/"
        ros_prefix = f"/{namespace}/"

        bridges.extend(
            [
                {
                    "ros_topic_name": f"{ros_prefix}scan",
                    "gz_topic_name": f"{gz_prefix}scan",
                    "ros_type_name": "sensor_msgs/msg/LaserScan",
                    "gz_type_name": "gz.msgs.LaserScan",
                    "direction": "GZ_TO_ROS",
                },
                {
                    "ros_topic_name": f"{ros_prefix}cmd_vel",
                    "gz_topic_name": f"{gz_prefix}cmd_vel",
                    "ros_type_name": "geometry_msgs/msg/Twist",
                    "gz_type_name": "gz.msgs.Twist",
                    "direction": "ROS_TO_GZ",
                },
                {
                    "ros_topic_name": f"{ros_prefix}joint_states",
                    "gz_topic_name": f"{gz_prefix}joint_states",
                    "ros_type_name": "sensor_msgs/msg/JointState",
                    "gz_type_name": "gz.msgs.Model",
                    "direction": "GZ_TO_ROS",
                },
                {
                    "ros_topic_name": f"{ros_prefix}odom",
                    "gz_topic_name": f"{gz_prefix}odom",
                    "ros_type_name": "nav_msgs/msg/Odometry",
                    "gz_type_name": "gz.msgs.Odometry",
                    "direction": "GZ_TO_ROS",
                },
            ]
        )

    bridge_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix="pinky_fleet_bridge_",
        suffix=".yaml",
        delete=False,
    )
    with bridge_file:
        yaml.safe_dump(bridges, bridge_file, sort_keys=False)

    return bridge_file.name


def _spawn_robots_and_bridges(context):
    robots_config = LaunchConfiguration("robots_config").perform(context)
    robots = _load_robot_specs(robots_config)
    upload_launch = os.path.join(
        get_package_share_directory("pinky_description"),
        "launch",
        "upload_robot.launch.py",
    )
    bridge_config_path = _write_bridge_config(robots)

    actions = [
        LogInfo(msg=f"Using robot config: {robots_config}"),
        LogInfo(msg=f"Generated bridge config: {bridge_config_path}"),
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="fleet_parameter_bridge",
            output="screen",
            arguments=["--ros-args", "-p", f"config_file:={bridge_config_path}"],
            parameters=[{"use_sim_time": True}],
        ),
    ]

    for robot in robots:
        namespace = robot["namespace"]
        robot_name = robot.get("robot_name", namespace)
        x = str(robot["x"])
        y = str(robot["y"])
        z = str(robot.get("z", 0.1))
        yaw = str(robot.get("yaw", 0.0))
        cam_tilt_deg = str(robot.get("cam_tilt_deg", 0))

        actions.extend(
            [
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(upload_launch),
                    launch_arguments={
                        "namespace": namespace,
                        "is_sim": "true",
                        "cam_tilt_deg": cam_tilt_deg,
                    }.items(),
                ),
                Node(
                    package="ros_gz_sim",
                    executable="create",
                    name=f"{namespace}_create",
                    output="screen",
                    arguments=[
                        "-name",
                        robot_name,
                        "-topic",
                        f"/{namespace}/robot_description",
                        "-x",
                        x,
                        "-y",
                        y,
                        "-z",
                        z,
                        "-Y",
                        yaw,
                    ],
                    parameters=[{"use_sim_time": True}],
                ),
            ]
        )

    return actions


def generate_launch_description():
    world_name = LaunchConfiguration("world_name")
    world = LaunchConfiguration("world")
    gz_partition = LaunchConfiguration("gz_partition")
    robots_config = LaunchConfiguration("robots_config")

    resource_path = [
        FindPackageShare("pinky_description"),
        "/../:",
        FindPackageShare("pinky_gz_sim"),
        ":",
        FindPackageShare("pinky_gz_sim"),
        "/worlds:",
        FindPackageShare("pinky_gz_sim"),
        "/models:",
        EnvironmentVariable("HOME"),
        "/.gazebo/models",
    ]

    return LaunchDescription(
        [
            DeclareLaunchArgument("world_name", default_value="fleet_practice_large.world"),
            DeclareLaunchArgument(
                "world",
                default_value=[FindPackageShare("pinky_gz_sim"), "/worlds/", world_name],
            ),
            DeclareLaunchArgument("gz_partition", default_value="pinky_fleet_sim"),
            DeclareLaunchArgument(
                "robots_config",
                default_value=[
                    FindPackageShare("pinky_fleet_sim"),
                    "/config/two_pinky_robots.yaml",
                ],
            ),
            OpaqueFunction(function=_cleanup_stale_gz_servers),
            SetEnvironmentVariable(name="GZ_PARTITION", value=gz_partition),
            SetEnvironmentVariable(name="GZ_SIM_RESOURCE_PATH", value=resource_path),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    [FindPackageShare("ros_gz_sim"), "/launch/gz_sim.launch.py"]
                ),
                launch_arguments={
                    "gz_args": ["-r -v4 ", world],
                    "on_exit_shutdown": "true",
                }.items(),
            ),
            OpaqueFunction(function=_spawn_robots_and_bridges),
        ]
    )
