from setuptools import setup

package_name = '__PKG__'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    extras_require={'test': ['pytest']},
    maintainer='DIT Robotics',
    maintainer_email='dit.robotics@gmail.com',
    description='TODO: one sentence on what __PKG__ does.',
    license='MIT',
    entry_points={'console_scripts': ['__NODE__ = __PKG__.__NODE__:main']},
)
