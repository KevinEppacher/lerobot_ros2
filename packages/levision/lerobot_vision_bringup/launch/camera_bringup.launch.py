import os
from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():

    # ---------------------- Paths ------------------------------#

    camera_config_dir = os.path.join(
        get_package_share_directory("lerobot_vision_bringup"),
        "config",
    )

    # ---------------------- Arguments ------------------------------#

    namespace_arg = DeclareLaunchArgument(
        "namespace",
        default_value="follower",
        description="Namespace for the camera",
    )

    camera_name_arg = DeclareLaunchArgument(
        "camera_name",
        default_value="wrist_camera",
        description="Name of the camera node",
    )

    config_file_arg = DeclareLaunchArgument(
        "config_file",
        default_value="follower_wrist_camera.yaml",
        description="Camera configuration file",
    )

    video_device_arg = DeclareLaunchArgument(
        "video_device",
        default_value="/dev/video0",
        description=(
            "Video device for the camera. "
            "List devices with 'v4l2-ctl --list-devices'."
        ),
    )

    namespace = LaunchConfiguration("namespace")
    camera_name = LaunchConfiguration("camera_name")
    config_file = LaunchConfiguration("config_file")
    video_device = LaunchConfiguration("video_device")

    # ---------------------- Nodes ------------------------------#

    cam_node = Node(
        package="usb_cam",
        executable="usb_cam_node_exe",
        name=camera_name,
        namespace=namespace,
        output="screen",
        parameters=[
            [camera_config_dir, "/", config_file],
            {"video_device": video_device}
        ],
    )

    # ---------------------- Launch Description ------------------------------#

    ld = LaunchDescription()
    ld.add_action(namespace_arg)
    ld.add_action(camera_name_arg)
    ld.add_action(config_file_arg)
    ld.add_action(video_device_arg)
    ld.add_action(cam_node)
    return ld
