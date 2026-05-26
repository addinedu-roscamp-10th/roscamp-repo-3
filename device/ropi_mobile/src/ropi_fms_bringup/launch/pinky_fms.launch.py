from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, PushROSNamespace, SetRemap
from launch_ros.substitutions import FindPackageShare
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    robot_id = LaunchConfiguration("robot_id")
    map_file = LaunchConfiguration("map")
    nav2_params_file = LaunchConfiguration("nav2_params_file")
    lidar_serial_port = LaunchConfiguration("lidar_serial_port")
    use_sim_time = LaunchConfiguration("use_sim_time")
    autostart = LaunchConfiguration("autostart")
    use_composition = LaunchConfiguration("use_composition")
    log_level = LaunchConfiguration("log_level")

    default_map_file = PathJoinSubstitution(
        [FindPackageShare("ropi_nav_config"), "maps", "map_0504.yaml"]
    )
    default_params_file = PathJoinSubstitution(
        [FindPackageShare("ropi_fms_bringup"), "config", "nav2_params_fms.yaml"]
    )
    robot_description_xacro = PathJoinSubstitution(
        [FindPackageShare("pinky_description"), "urdf", "robot.urdf.xacro"]
    )
    pinky_bringup_params = PathJoinSubstitution(
        [FindPackageShare("pinky_bringup"), "config", "pinky_params.yaml"]
    )
    sllidar_launch = PathJoinSubstitution(
        [FindPackageShare("sllidar_ros2"), "launch", "sllidar_c1_launch.py"]
    )
    pinky_localization_launch = PathJoinSubstitution(
        [FindPackageShare("pinky_navigation"), "launch", "localization_launch.xml"]
    )
    pinky_navigation_launch = PathJoinSubstitution(
        [FindPackageShare("pinky_navigation"), "launch", "navigation_launch.xml"]
    )
    namespaced_localization_params = RewrittenYaml(
        source_file=nav2_params_file,
        param_rewrites={},
        root_key=robot_id,
        convert_types=True,
    )
    namespaced_navigation_params = RewrittenYaml(
        source_file=nav2_params_file,
        param_rewrites={},
        root_key=robot_id,
        convert_types=True,
    )

    robot_description = Command(
        [
            "xacro ",
            robot_description_xacro,
            " namespace:=",
            "",
            " is_sim:=false",
            " sim_type:=gz_sim",
            " cam_tilt_deg:=0",
            " screen_tilt_deg:=-25",
        ]
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        namespace=robot_id,
        output="screen",
        parameters=[
            {
                "ignore_timestamp": False,
                "use_sim_time": use_sim_time,
                "robot_description": robot_description,
                "frame_prefix": "",
            }
        ],
        remappings=[
            ("/tf", "tf"),
            ("/tf_static", "tf_static"),
        ],
    )

    joint_state_publisher = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        name="joint_state_publisher",
        namespace=robot_id,
        output="screen",
        parameters=[
            {
                "source_list": ["joint_states"],
                "rate": 20.0,
                "use_sim_time": use_sim_time,
            }
        ],
    )

    pinky_drive = Node(
        package="pinky_bringup",
        executable="bringup",
        namespace=robot_id,
        output="screen",
        parameters=[pinky_bringup_params],
        remappings=[
            ("/tf", "tf"),
            ("/tf_static", "tf_static"),
        ],
    )

    battery_publisher = Node(
        package="pinky_bringup",
        executable="battery_publisher",
        namespace=robot_id,
        output="screen",
    )

    rplidar_bringup = GroupAction(
        [
            PushROSNamespace(robot_id),
            SetRemap(src="/scan", dst="scan"),
            SetRemap(src="/tf", dst="tf"),
            SetRemap(src="/tf_static", dst="tf_static"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(sllidar_launch),
                launch_arguments={
                    "serial_port": lidar_serial_port,
                    "frame_id": "rplidar_link",
                    "inverted": "false",
                    "angle_compensate": "true",
                    "scan_mode": "DenseBoost",
                }.items(),
            ),
        ]
    )

    nav2_bringup = GroupAction(
        [
            PushROSNamespace(robot_id),
            IncludeLaunchDescription(
                XMLLaunchDescriptionSource(pinky_localization_launch),
                launch_arguments={
                    "namespace": "",
                    "params_file": namespaced_localization_params,
                    "map": map_file,
                    "use_sim_time": use_sim_time,
                    "autostart": autostart,
                    "use_composition": use_composition,
                    "use_respawn": "False",
                    "container_name": "nav2_container",
                    "log_level": log_level,
                    "lifecycle_nodes": "['map_server', 'amcl']",
                }.items(),
            ),
            IncludeLaunchDescription(
                XMLLaunchDescriptionSource(pinky_navigation_launch),
                launch_arguments={
                    "namespace": "",
                    "params_file": namespaced_navigation_params,
                    "use_sim_time": use_sim_time,
                    "autostart": autostart,
                    "use_composition": use_composition,
                    "use_respawn": "False",
                    "container_name": "nav2_container",
                    "log_level": log_level,
                    "lifecycle_nodes": "['controller_server', 'smoother_server', 'planner_server', 'behavior_server', 'bt_navigator', 'waypoint_follower', 'velocity_smoother']",
                }.items(),
            ),
        ]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_id", default_value="pinky1"),
            DeclareLaunchArgument("map", default_value=default_map_file),
            DeclareLaunchArgument("nav2_params_file", default_value=default_params_file),
            DeclareLaunchArgument("lidar_serial_port", default_value="/dev/ttyS0"),
            DeclareLaunchArgument("use_sim_time", default_value="False"),
            DeclareLaunchArgument("autostart", default_value="True"),
            DeclareLaunchArgument("use_composition", default_value="False"),
            DeclareLaunchArgument("log_level", default_value="info"),
            robot_state_publisher,
            joint_state_publisher,
            pinky_drive,
            battery_publisher,
            rplidar_bringup,
            nav2_bringup,
        ]
    )
