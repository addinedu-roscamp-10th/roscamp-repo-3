from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'tracking'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*launch.py') + glob('launch/*.xml')),
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    package_data={
        package_name: ['visitor_approval_dialog.png'],
    },
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
            'tracking = tracking.tracking:main',
            're_search = tracking.re_search:main',
            'mission_manager = tracking.mission_manager:main',
            'cmd_vel_mux = tracking.cmd_vel_mux:main',
        ],
    },
)
