import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'ropi_delivery'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config', 'pinky2'), glob('config/pinky2/*.yaml')),
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
            'pinky_navigation_action_server = ropi_delivery.mobile_controller_test:main',
            'mobile_controller_test = ropi_delivery.mobile_controller_test:main',
            'transport_control_node = ropi_delivery.transport_control_node:main',
        ],
    },
)
