import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration

from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_demo_launch


def launch_setup(context, *args, **kwargs):
    port = LaunchConfiguration("port").perform(context)
    calibration_path = LaunchConfiguration("calibration_path").perform(context)

    workcell_xacro = os.path.join(
        get_package_share_directory("lerobot_moveit_config"),
        "config",
        "lerobot_workcell.urdf.xacro",
    )

    moveit_config = (
        MoveItConfigsBuilder(
            "lerobot_workcell",
            package_name="lerobot_moveit_config",
        )
        .robot_description(
            file_path=workcell_xacro,
            mappings={
                "port": port,
                "calibration_file": calibration_path,
                "robot_plugin": "hiwonder_lerobot_cpp/Leader",
            },
        )
        .to_moveit_configs()
    )

    return generate_demo_launch(moveit_config).entities


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "port",
                default_value="/dev/ttyACM0",
            ),
            DeclareLaunchArgument(
                "calibration_path",
                default_value=(
                    "/app/src/lemodel/so101_description/"
                    "config/leader_example_calibration.yaml"
                ),
            ),
            OpaqueFunction(function=launch_setup),
        ]
    )
