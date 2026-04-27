from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    robot_id = LaunchConfiguration("robot_id")
    params_file = LaunchConfiguration("params_file")
    default_params_file = PathJoinSubstitution(
        [FindPackageShare("fallen_detection"), "config", robot_id, "patrol.yaml"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_id", default_value="pinky3"),
            DeclareLaunchArgument("params_file", default_value=default_params_file),
            Node(
                package="fallen_detection",
                executable="fallen_detection_client_tcp",
                name="fallen_detection_client_tcp",
                output="screen",
                parameters=[params_file],
            ),
        ]
    )
