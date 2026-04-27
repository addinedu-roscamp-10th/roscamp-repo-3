from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    robot_id = LaunchConfiguration("robot_id")
    params_file = LaunchConfiguration("params_file")
    default_params_file = PathJoinSubstitution(
        [FindPackageShare("ropi_arm_control"), "config", robot_id, "arm.yaml"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_id", default_value="jetcobot1"),
            DeclareLaunchArgument("params_file", default_value=default_params_file),
            Node(
                package="ropi_arm_control",
                executable="jet_arm_node",
                name="jet_arm_node",
                output="screen",
                parameters=[params_file],
            ),
        ]
    )
