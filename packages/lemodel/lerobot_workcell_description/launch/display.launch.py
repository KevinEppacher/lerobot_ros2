import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    # ---------------------- Arguments ------------------------------#

    sim_time_arg = DeclareLaunchArgument(
        "use_sim_time", default_value="false", description="Flag to enable use_sim_time"
    )

    use_sim_time = LaunchConfiguration("use_sim_time")

    gui_arg = DeclareLaunchArgument(
        "gui",
        default_value="true",
        description="Flag to enable joint_state_publisher_gui",
    )

    gui = LaunchConfiguration("gui")

    # ---------------------- Paths ------------------------------#

    path_to_urdf = os.path.join(
        get_package_share_directory("lerobot_workcell_description"),
        "urdf",
        "workcell.urdf.xacro",
    )

    rviz_config_file = os.path.join(
        get_package_share_directory("lerobot_workcell_description"),
        "rviz",
        "rviz.rviz"
    )

    robot_description = ParameterValue(
        Command(["xacro", " ", path_to_urdf]), value_type=str
    )

    # ---------------------- Nodes ------------------------------#

    joint_state_publisher_gui = Node(
        package="joint_state_publisher_gui",
        executable="joint_state_publisher_gui",
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time, "robot_description": robot_description}
        ],
        condition=IfCondition(gui),
    )

    joint_state_publisher_node = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
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
        output="screen",
        parameters=[
            {"use_sim_time": use_sim_time, "robot_description": robot_description}
        ],
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        output="screen",
        arguments=["-d", rviz_config_file],
        condition=IfCondition(gui),
    )

    ld = LaunchDescription()
    ld.add_action(sim_time_arg)
    ld.add_action(gui_arg)
    ld.add_action(joint_state_publisher_gui)
    ld.add_action(joint_state_publisher_node)
    ld.add_action(robot_state_publisher_node)
    ld.add_action(rviz)
    return ld
