from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    # ---------------------- Arguments ------------------------------#

    namespace_arg = DeclareLaunchArgument(
        "namespace",
        default_value="follower",
        description="Namespace for the robot",
    )

    port_arg = DeclareLaunchArgument(
        "port",
        default_value="/dev/ttyACM1",
        description=(
            "Serial port of the HiWonder servo bus. "
            "Persistent /dev/serial/by-id/ paths are recommended."
        ),
    )

    calibration_path_arg = DeclareLaunchArgument(
        "calibration_path",
        default_value=PathJoinSubstitution(
            [
                FindPackageShare("so101_description"),
                "config",
                "follower_example_calibration.yaml",
            ]
        ),
        description="Path to the SO-101 calibration file",
    )

    gui_arg = DeclareLaunchArgument(
        "gui",
        default_value="false",
        description="Enable RViz",
    )

    namespace = LaunchConfiguration("namespace")
    port = LaunchConfiguration("port")
    calibration_path = LaunchConfiguration("calibration_path")
    gui = LaunchConfiguration("gui")

    # ---------------------- Follower Bringup ------------------------------#

    follower_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution(
                [
                    FindPackageShare("lerobot_bringup"),
                    "launch",
                    "so101_follower_bringup.launch.py",
                ]
            )
        ),
        launch_arguments={
            "namespace": namespace,
            "port": port,
            "calibration_path": calibration_path,
            "gui": gui,
            "description_package": "lerobot_workcell_description",
            "description_file": "urdf/workcell.urdf.xacro",
        }.items(),
    )

    # ---------------------- Launch Description ------------------------------#

    ld = LaunchDescription()
    ld.add_action(namespace_arg)
    ld.add_action(port_arg)
    ld.add_action(calibration_path_arg)
    ld.add_action(gui_arg)
    ld.add_action(follower_bringup)

    return ld
