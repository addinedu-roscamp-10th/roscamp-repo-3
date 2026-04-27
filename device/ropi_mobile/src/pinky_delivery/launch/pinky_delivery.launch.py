from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    robot_id = LaunchConfiguration("robot_id")
    params_file = LaunchConfiguration("params_file")
    default_params_file = PathJoinSubstitution(
        [FindPackageShare("pinky_delivery"), "config", robot_id, "delivery.yaml"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_id", default_value="pinky2"),
            DeclareLaunchArgument("params_file", default_value=default_params_file),
            Node(
                package="pinky_delivery",
                executable="pinky_navigation_action_server",
                name="pinky_amr_node",
                output="screen",
                parameters=[params_file],
            ),
        ]
    )
