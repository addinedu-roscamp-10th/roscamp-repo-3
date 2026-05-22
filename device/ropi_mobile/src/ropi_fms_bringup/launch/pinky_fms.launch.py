from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource
from launch_ros.actions import Node, PushROSNamespace, SetRemap
from launch_ros.parameter_descriptions import ParameterFile
from launch_ros.substitutions import FindPackageShare
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    robot_id = LaunchConfiguration("robot_id")
    map_file = LaunchConfiguration("map")
    params_file = LaunchConfiguration("params_file")
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
    robot_controllers = PathJoinSubstitution(
        [FindPackageShare("ropi_fms_bringup"), "config", "pinky_controllers_fms.yaml"]
    )
    sllidar_launch = PathJoinSubstitution(
        [FindPackageShare("sllidar_ros2"), "launch", "sllidar_c1_launch.py"]
    )
    pinky_navigation_launch = PathJoinSubstitution(
        [FindPackageShare("pinky_navigation"), "launch", "bringup_launch.xml"]
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

    controller_manager = Node(
        package="controller_manager",
        executable="ros2_control_node",
        namespace=robot_id,
        output="both",
        parameters=[
            ParameterFile(
                RewrittenYaml(
                    source_file=robot_controllers,
                    param_rewrites={},
                    root_key=robot_id,
                ),
                allow_substs=True,
            ),
        ],
        remappings=[
            ("~/robot_description", "robot_description"),
            ("base_controller/cmd_vel", "cmd_vel"),
            ("base_controller/odom", "odom"),
            ("/tf", "tf"),
            ("/tf_static", "tf_static"),
        ],
    )

    load_base_controller = Node(
        package="controller_manager",
        executable="spawner",
        namespace=robot_id,
        output="screen",
        arguments=["base_controller", "--controller-manager", "controller_manager"],
    )
    load_gpio_controller = Node(
        package="controller_manager",
        executable="spawner",
        namespace=robot_id,
        output="screen",
        arguments=["gpio_controller", "--controller-manager", "controller_manager"],
    )
    load_joint_state_broadcaster = Node(
        package="controller_manager",
        executable="spawner",
        namespace=robot_id,
        output="screen",
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager",
            "controller_manager",
        ],
    )
    delay_gpio_after_base_controller_spawner = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=load_base_controller,
            on_exit=[load_gpio_controller],
        )
    )
    delay_joint_state_broadcaster_after_gpio_controller_spawner = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=load_gpio_controller,
            on_exit=[load_joint_state_broadcaster],
        )
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
                    "serial_port": "/dev/ttyAMA0",
                    "frame_id": "rplidar_link",
                    "inverted": "false",
                    "angle_compensate": "true",
                    "scan_mode": "DenseBoost",
                }.items(),
            ),
        ]
    )

    nav2_bringup = IncludeLaunchDescription(
        XMLLaunchDescriptionSource(pinky_navigation_launch),
        launch_arguments={
            "namespace": robot_id,
            "params_file": params_file,
            "map": map_file,
            "use_sim_time": use_sim_time,
            "autostart": autostart,
            "use_composition": use_composition,
            "container_name": "nav2_container",
            "log_level": log_level,
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_id", default_value="pinky1"),
            DeclareLaunchArgument("map", default_value=default_map_file),
            DeclareLaunchArgument("params_file", default_value=default_params_file),
            DeclareLaunchArgument("use_sim_time", default_value="False"),
            DeclareLaunchArgument("autostart", default_value="True"),
            DeclareLaunchArgument("use_composition", default_value="False"),
            DeclareLaunchArgument("log_level", default_value="info"),
            robot_state_publisher,
            joint_state_publisher,
            controller_manager,
            load_base_controller,
            delay_gpio_after_base_controller_spawner,
            delay_joint_state_broadcaster_after_gpio_controller_spawner,
            rplidar_bringup,
            nav2_bringup,
        ]
    )
