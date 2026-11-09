import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import (
    PathJoinSubstitution,
)

def generate_launch_description():

    # ---------------------- Paths ------------------------------#

    so101_description_share = get_package_share_directory(
        "so101_description"
    )

    lerobot_bringup_share = get_package_share_directory(
        "lerobot_bringup"
    )

    robot_type = LaunchConfiguration("robot_type")
    description_package = LaunchConfiguration("description_package")
    description_file = LaunchConfiguration("description_file")

    dof = LaunchConfiguration("dof")

    # An explicit description_file overrides the DOF-based default.
    xacro_file = PathJoinSubstitution(
        [
            FindPackageShare(description_package),
            PythonExpression(
                [
                    "'", description_file, "' or 'urdf/robots/so101_",
                    dof, "dof.urdf.xacro'",
                ]
            ),
        ]
    )

    # Only a 5DOF example calibration exists; 6DOF requires an explicit file.
    # One controllers file per DOF, listing the matching joints.
    controllers_file = [
        os.path.join(lerobot_bringup_share, "config", "so101_"),
        LaunchConfiguration("dof"),
        "dof_controllers.yaml",
    ]

    # Concatenated substitutions: <share>/rviz/<robot_type>.rviz
    rviz_config_file = [
        os.path.join(so101_description_share, "rviz", ""),
        robot_type,
        ".rviz",
    ]

    # ---------------------- Arguments ------------------------------#

    dof_arg = DeclareLaunchArgument(
        "dof",
        default_value="5",
        choices=["5", "6"],
        description="Robot degrees of freedom",
    )

    robot_type_arg = DeclareLaunchArgument(
        "robot_type",
        default_value="follower",
        choices=["leader", "follower"],
        description="Robot role; selects plugin, RViz config and defaults",
    )

    namespace_arg = DeclareLaunchArgument(
        "namespace",
        default_value=robot_type,
        description="Namespace for the robot",
    )

    port_arg = DeclareLaunchArgument(
        "port",
        default_value=PythonExpression(
            [
                "'/dev/ttyACM0' if '", robot_type,
                "' == 'leader' else '/dev/ttyACM1'",
            ]
        ),
        description=(
            "Serial port of the HiWonder servo bus. "
            "Persistent /dev/serial/by-id/ paths are recommended."
        ),
    )

    calibration_path_argument = DeclareLaunchArgument(
        "calibration_path",
        default_value=[
            os.path.join(so101_description_share, "config", ""),
            dof,
            "dof/",
            robot_type,
            "_example_calibration.yaml",
        ],
        description="Path to the SO-101 calibration file",
    )

    gui_arg = DeclareLaunchArgument(
        "gui",
        default_value="false",
        description="Enable RViz",
    )

    description_package_arg = DeclareLaunchArgument(
        "description_package",
        default_value="so101_description",
        description="Package containing the robot description",
    )

    description_file_arg = DeclareLaunchArgument(
        "description_file",
        default_value="",
        description=(
            "Relative path to the Xacro description. "
            "Defaults to the description matching dof."
        ),
    )

    port = LaunchConfiguration("port")
    calibration_path = LaunchConfiguration("calibration_path")
    gui = LaunchConfiguration("gui")
    namespace = LaunchConfiguration("namespace")

    # ---------------------- Robot Description ------------------------------#

    robot_description = ParameterValue(
        Command(
            [
                "xacro ",
                xacro_file,
                " port:=",
                port,
                " calibration_file:=",
                calibration_path,
                " prefix:=",
                namespace,
                "_",
                " robot_plugin:=hiwonder_lerobot_cpp/Robot",
            ]
        ),
        value_type=str,
    )

    # ---------------------- Nodes ------------------------------#

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="screen",
        namespace=namespace,
        parameters=[
            {
                "robot_description": robot_description,
            }
        ],
    )

    controller_manager_path = PathJoinSubstitution(
        ["/", namespace, "controller_manager"]
    )

    controller_manager = Node(
        package="controller_manager",
        executable="ros2_control_node",
        output="screen",
        namespace=namespace,
        emulate_tty=True,
        parameters=[
            {
                "robot_description": robot_description,
            },
            controllers_file,
        ],
    )

    joint_state_broadcaster = Node(
        package="controller_manager",
        executable="spawner",
        namespace=namespace,
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager",
            controller_manager_path,
        ],
        output="screen",
    )

    position_controller = Node(
        package="controller_manager",
        executable="spawner",
        namespace=namespace,
        arguments=[
            "position_controller",
            "--controller-manager",
            controller_manager_path,
        ],
        output="screen",
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        output="screen",
        arguments=[
            "-d",
            rviz_config_file,
        ],
        condition=IfCondition(gui),
    )
    
    lerobot_control_node = Node(
        package='lerobot_control',
        executable='control_mode_manager',
        namespace=namespace,
        output='screen',
        emulate_tty=True,
        parameters=[{
            'controller_manager': 'controller_manager',
            'service_timeout': 5.0,
        }],
    )

    # ---------------------- Launch Description ------------------------------#

    ld = LaunchDescription()
    ld.add_action(robot_type_arg)
    ld.add_action(dof_arg)
    ld.add_action(port_arg)
    ld.add_action(calibration_path_argument)
    ld.add_action(gui_arg)
    ld.add_action(namespace_arg)
    ld.add_action(description_package_arg)
    ld.add_action(description_file_arg)
    ld.add_action(robot_state_publisher)
    ld.add_action(controller_manager)
    ld.add_action(joint_state_broadcaster)
    ld.add_action(position_controller)
    ld.add_action(rviz)
    ld.add_action(lerobot_control_node)
    return ld
