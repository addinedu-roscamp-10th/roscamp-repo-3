from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import XMLLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    robot_id = LaunchConfiguration("robot_id")
    params_file = LaunchConfiguration("params_file")
    map_file = LaunchConfiguration("map")
    use_sim_time = LaunchConfiguration("use_sim_time")

    default_params_file = PathJoinSubstitution(
        [FindPackageShare("ropi_pinky_config"), "config", robot_id, "nav2_params.yaml"]
    )
    default_map_file = PathJoinSubstitution(
        [FindPackageShare("ropi_pinky_config"), "maps", robot_id, "map.yaml"]
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
            IncludeLaunchDescription(
                XMLLaunchDescriptionSource(pinky_bringup_launch),
                launch_arguments={
                    "params_file": params_file,
                    "map": map_file,
                    "use_sim_time": use_sim_time,
                }.items(),
            ),
        ]
    )
