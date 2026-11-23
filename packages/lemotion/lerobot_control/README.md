# lerobot_control

## Overview

`lerobot_control` provides the `control_mode_manager` node. It coordinates
switches between idle, teleoperation, and trajectory controllers for one arm.

## ROS 2 Interface

The relative service `set_control_mode` accepts a mode and returns a success
flag and a diagnostic message. See
[`lerobot_interfaces/srv/SetControlMode`](../lerobot_interfaces/srv/SetControlMode.srv).

| Mode | Managed controllers active |
| --- | --- |
| `IDLE` (0) | None |
| `TELEOP` (1) | `position_controller` |
| `TRAJECTORY` (2) | `manipulator_controller` and `gripper_controller` |

Load and configure the controllers needed for the requested mode before
calling the service. The node verifies the resulting controller states before
reporting success. It switches only the controllers listed above. `IDLE`
changes controller activation and leaves motor torque unchanged.

If a switch request times out while awaiting a response, the resulting
controller state may be uncertain. The node rejects further mode requests for
the lifetime of that instance.

## Usage and Configuration

[SO-101 bringup](../../lebringup/lerobot_bringup/launch/so101_bringup.launch.py)
starts a mode manager in each arm's namespace. For example, the follower
service is `/follower/set_control_mode`. Teleoperation uses each arm's service
to request its control mode.

The `controller_manager` parameter identifies the target manager. Its relative
default, `controller_manager`, resolves within the node's namespace.
`service_timeout` sets the timeout in seconds for controller manager service
operations. It defaults to five seconds and must be positive.

## Architecture

The mode manager switches controllers through the ROS 2 controller manager.
The [`lerobot_ros2_control` hardware adapter](../lerobot_ros2_control/)
handles hardware I/O and loads a backend selected by the URDF
`robot_plugin` parameter. For plugin development, see the
[`lerobot::Robot` contract](../lerobot_cpp/include/lerobot_cpp/robot.hpp) and
the [HiWonder plugin registration](../hiwonder_lerobot_cpp/hiwonder_lerobot_cpp_plugins.xml).
