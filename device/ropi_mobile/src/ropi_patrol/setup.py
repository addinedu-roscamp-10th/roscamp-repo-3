import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'ropi_patrol'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config', 'pinky3'), glob('config/pinky3/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pinky',
    maintainer_email='pinky@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            "fallen_detection_client = ropi_patrol.fallen_detection_client:main",
            "ropi_camera = ropi_patrol.ropi_camera:main",
            "patrol_path_action_server = ropi_patrol.patrol_path_action_server:main",
            "fallen_alarm_buzzer = ropi_patrol.fallen_alarm_buzzer:main",
        ],
    },
)
