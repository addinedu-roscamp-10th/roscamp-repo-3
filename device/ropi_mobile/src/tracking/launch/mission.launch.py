from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    nav2_params = PathJoinSubstitution([
        FindPackageShare('tracking'),
        'config',
        'nav2_params_mux.yaml'
    ])

    pinky_navigation = IncludeLaunchDescription(
        AnyLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('tracking'),
                'launch',
                'bringup_mux.launch.xml'
            ])
        ),
        launch_arguments={
            'map': 'map_final.yaml',
            'params_file': nav2_params,
        }.items()
    )

    return LaunchDescription([
        pinky_navigation,
        Node(package='tracking', executable='tracking', name='tracking_node', output='screen'),
        Node(package='tracking', executable='re_search', name='re_search_node', output='screen'),
        Node(package='tracking', executable='mission_manager', name='mission_manager', output='screen'),
        Node(package='tracking', executable='cmd_vel_mux', name='cmd_vel_mux', output='screen'),
    ])