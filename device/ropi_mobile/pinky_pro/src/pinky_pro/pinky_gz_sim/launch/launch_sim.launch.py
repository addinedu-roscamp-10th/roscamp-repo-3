import os
import signal
import time

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
        LogInfo(
            msg=(
                f"Killed stale Gazebo server pid={pid}: {cmdline}"
            )
        )
        for pid, cmdline in killed_processes
    ]

    messages.extend(
        LogInfo(
            msg=(
                f"Failed to stop stale Gazebo server pid={pid}: {cmdline}"
            )
        )
        for pid, cmdline in stale_processes
    )

    return messages


def generate_launch_description():
    namespace = LaunchConfiguration("namespace")
    robot_name = LaunchConfiguration("robot_name")
    cam_tilt_deg = LaunchConfiguration("cam_tilt_deg")
    gz_partition = LaunchConfiguration("gz_partition")
    world_name = LaunchConfiguration("world_name")
    world = LaunchConfiguration("world")
    bridge_params = LaunchConfiguration("bridge_params")

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

    return LaunchDescription([
        DeclareLaunchArgument("namespace", default_value=""),
        DeclareLaunchArgument("robot_name", default_value=[namespace, "pinky"]),
        DeclareLaunchArgument("cam_tilt_deg", default_value="0"),
        DeclareLaunchArgument("gz_partition", default_value="pinky_pro_sim"),
        DeclareLaunchArgument("world_name", default_value="pinky_factory.world"),
        DeclareLaunchArgument(
            "world",
            default_value=[FindPackageShare("pinky_gz_sim"), "/worlds/", world_name],
        ),
        DeclareLaunchArgument(
            "bridge_params",
            default_value=[FindPackageShare("pinky_gz_sim"), "/params/pinky_bridge.yaml"],
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
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                [FindPackageShare("pinky_description"), "/launch/upload_robot.launch.py"]
            ),
            launch_arguments={
                "namespace": namespace,
                "is_sim": "true",
                "cam_tilt_deg": cam_tilt_deg,
            }.items(),
        ),
        Node(
            package="ros_gz_sim",
            executable="create",
            name="create",
            output="screen",
            arguments=[
                "-name", robot_name,
                "-topic", [namespace, "/robot_description"],
                "-x", "0.0",
                "-y", "0.0",
                "-z", "0.1",
            ],
            parameters=[{"use_sim_time": True}],
        ),
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            name="parameter_bridge",
            output="screen",
            arguments=["--ros-args", "-p", ["config_file:=", bridge_params]],
        ),
        Node(
            package="ros_gz_image",
            executable="image_bridge",
            name="image_bridge_raw",
            output="screen",
            arguments=["/camera/image_raw"],
        ),
        Node(
            package="ros_gz_image",
            executable="image_bridge",
            name="image_bridge_camera",
            output="screen",
            arguments=["/camera"],
        ),
    ])
