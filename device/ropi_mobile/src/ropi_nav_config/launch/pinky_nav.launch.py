from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    robot_id = LaunchConfiguration("robot_id")
    params_file = LaunchConfiguration("params_file")
    map_file = LaunchConfiguration("map")
    use_sim_time = LaunchConfiguration("use_sim_time")
    status_odom_topic = LaunchConfiguration("status_odom_topic")
    status_state_topic = LaunchConfiguration("status_state_topic")
    status_battery_voltage_topic = LaunchConfiguration("status_battery_voltage_topic")

    default_params_file = PathJoinSubstitution(
        [FindPackageShare("ropi_nav_config"), "config", "nav2_params.yaml"]
    )
    default_map_file = PathJoinSubstitution(
        [FindPackageShare("ropi_nav_config"), "maps", "map_0504.yaml"]
    )
    pinky_bringup_launch = PathJoinSubstitution(
        [FindPackageShare("pinky_navigation"), "launch", "bringup_launch.xml"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_id", default_value="pinky2"),
            DeclareLaunchArgument("params_file", default_value=default_params_file),
            DeclareLaunchArgument("map", default_value=default_map_file),
            DeclareLaunchArgument("use_sim_time", default_value="False"),
            DeclareLaunchArgument("status_odom_topic", default_value="/odom"),
            DeclareLaunchArgument("status_state_topic", default_value="/transport/amr_status"),
            DeclareLaunchArgument(
                "status_battery_voltage_topic",
                default_value="/battery/voltage",
            ),
            IncludeLaunchDescription(
                XMLLaunchDescriptionSource(pinky_bringup_launch),
                launch_arguments={
                    "params_file": params_file,
                    "map": map_file,
                    "use_sim_time": use_sim_time,
                }.items(),
            ),
            Node(
                package="ropi_mobile_status_test",
                executable="pinky_status_runtime_publisher.py",
                name="pinky_status_runtime_publisher",
                output="screen",
                parameters=[
                    {
                        "pinky_id": robot_id,
                        "odom_topic": status_odom_topic,
                        "state_topic": status_state_topic,
                        "battery_voltage_topic": status_battery_voltage_topic,
                        "use_sim_time": use_sim_time,
                    }
                ],
            ),
        ]
    )
