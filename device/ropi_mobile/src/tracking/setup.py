from setuptools import setup
import os
from glob import glob

package_name = 'tracking'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='you',
    maintainer_email='you@example.com',
    description='Tracking node',
    license='Apache-2.0',

    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config', 'pinky1'),
            glob('config/pinky1/*.yaml')),
    ],

    entry_points={
        'console_scripts': [
            'tracking = tracking.tracking_node:main',
        ],
    },
)
