import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import (
    Command,
    LaunchConfiguration,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    # ---------------------- Arguments ------------------------------#

    sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false",
        description="Flag to enable use_sim_time",
    )

    gui_arg = DeclareLaunchArgument(
        "gui",
        default_value="true",
        description="Flag to enable joint_state_publisher_gui",
    )

    robot_type_arg = DeclareLaunchArgument(
        "robot_type",
        default_value="follower",
        choices=["leader", "follower"],
        description="Robot type",
    )

    dof_arg = DeclareLaunchArgument(
        "dof",
        default_value="5",
        choices=["5", "6"],
        description="Robot degrees of freedom",
    )

    use_sim_time = LaunchConfiguration("use_sim_time")
    gui = LaunchConfiguration("gui")
    robot_type = LaunchConfiguration("robot_type")
    dof = LaunchConfiguration("dof")

    # ---------------------- Paths ------------------------------#

    package_share = get_package_share_directory("so101_description")

    path_to_urdf = PythonExpression([
        "'",
        os.path.join(package_share, "urdf", "robots", "so101_"),
        "' + '",
        dof,
        "' + 'dof.urdf.xacro'",
    ])

    rviz_config_file = PythonExpression([
        "'",
        os.path.join(package_share, "rviz", ""),
        "' + '",
        robot_type,
        "' + '.rviz'",
    ])

    # ---------------------- Robot Description ------------------------------#

    robot_description = ParameterValue(
        Command([
            "xacro ",
            path_to_urdf,
            " prefix:=",
            robot_type,
            "_",
        ]),
        value_type=str,
    )

    # ---------------------- Nodes ------------------------------#

    joint_state_publisher_gui = Node(
        package="joint_state_publisher_gui",
        executable="joint_state_publisher_gui",
        namespace=robot_type,
        output="screen",
        parameters=[
            {
                "use_sim_time": use_sim_time,
                "robot_description": robot_description,
            }
        ],
        condition=IfCondition(gui),
    )

    joint_state_publisher_node = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        namespace=robot_type,
        output="screen",
        parameters=[
            {
                "use_sim_time": use_sim_time,
                "robot_description": robot_description,
            }
        ],
        condition=UnlessCondition(gui),
    )

    robot_state_publisher_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        namespace=robot_type,
        output="screen",
        parameters=[
            {
                "use_sim_time": use_sim_time,
                "robot_description": robot_description,
            }
        ],
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        output="screen",
        arguments=["-d", rviz_config_file],
        condition=IfCondition(gui),
    )

    # ---------------------- Launch Description ------------------------------#

    ld = LaunchDescription()
    ld.add_action(sim_time_arg)
    ld.add_action(gui_arg)
    ld.add_action(robot_type_arg)
    ld.add_action(dof_arg)
    ld.add_action(joint_state_publisher_gui)
    ld.add_action(joint_state_publisher_node)
    ld.add_action(robot_state_publisher_node)
    ld.add_action(rviz)
    return ld
