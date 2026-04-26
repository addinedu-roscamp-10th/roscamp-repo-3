import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'jet_arm_control'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=[]),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config', 'jetcobot1'), glob('config/jetcobot1/*.yaml')),
        (os.path.join('share', package_name, 'config', 'jetcobot2'), glob('config/jetcobot2/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jetcobot',
    maintainer_email='jetcobot@todo.todo',
    description='JetCobot arm control package',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'jet_arm_node = jet_arm_control.arm1_node:main',
        ],
    },
)
