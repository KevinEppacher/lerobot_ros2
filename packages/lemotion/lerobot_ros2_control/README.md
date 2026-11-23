# lerobot_ros2_control

## Overview

`lerobot_ros2_control` exports the
[`lerobot_ros2_control/LeRobotSystemHardware` system plugin](lerobot_ros2_control.xml).
It maps ROS 2 joint commands and feedback to a robot hardware backend.

## Architecture

The ROS 2 controller manager loads the system plugin from the robot description.
The system plugin loads a [`lerobot::Robot` backend](../lerobot_cpp/README.md)
through pluginlib. The stock SO-101 descriptions select
[`hiwonder_lerobot_cpp/Robot`](../hiwonder_lerobot_cpp/README.md), which handles
servo communication through [`hiwonder_servo_driver`](../hiwonder_servo_driver/README.md).

## Configuration

Set these hardware parameters in the URDF's `ros2_control` block.

| Parameter | Purpose |
| --- | --- |
| `robot_plugin` | Required pluginlib lookup name for the backend. |
| `port` | Required serial device path passed to the backend. |
| `baud_rate` | Required serial baud rate passed to the backend. |
| `calibration_file` | Required path to the joint calibration YAML. |
| `joint_prefix` | Optional prefix stripped from every controlled joint name for calibration lookup. Defaults to empty. |

Every controlled joint, including the gripper when present, must exist in the
URDF. Declare exactly one `position` command interface with numeric `min` and
`max` bounds, where `min < max`. Declare exactly three state interfaces in
this order: `position`, `velocity`, `current`. The framework exports these
interfaces from the URDF declarations. See the
[SO-101 control Xacros](../../lemodel/so101_description/urdf/control/).

Each controlled joint needs a calibration entry with a unique integer
`servo_id` from 0 to 253 and distinct signed 16-bit `lower_position` and
`upper_position` endpoints. Inverted raw endpoints are supported. The adapter
passes motor IDs to the backend in `ros2_control` joint declaration order.
Commands and feedback must follow that order. If `joint_prefix` is set, all
controlled joint names must start with it and the YAML keys omit it. See the
[calibration guide and examples](../../lemodel/so101_description/config/README.md).

The adapter maps raw positions to the configured joint bounds and uses the
same calibration slope for velocity. Backends supply velocity in raw position
ticks per second and current in milliamps, which the adapter converts to amps.
Position commands are clamped to the configured bounds before conversion.
If the backend rejects the converted targets, the adapter logs a warning and
skips the write. Read and write failures are reported to the controller manager.

## Usage

Use [SO-101 bringup](../../lebringup/lerobot_bringup/README.md) with the matching
robot description and calibration. Bringup starts the controller manager.
[MoveIt](../lerobot_moveit_config/README.md) connects to the arm and gripper
trajectory controllers started by bringup.

The adapter validates parameters at initialization and connects to the backend
during hardware configuration. Activation synchronizes position commands to
the measured positions before enabling torque. Deactivation disables torque.
Cleanup disconnects and releases the backend.

The hardware node's private `~/guiding_mode` service
(`std_srvs/srv/SetBool`) acknowledges the request when queued. The write cycle
applies the change. Guiding disables torque and suppresses position writes.
Leaving guiding mode synchronizes commands to measured positions before
re-enabling torque.

## Testing

From a built workspace, run the hardware-free tests for calibration conversion,
servo ID ordering, and initialization.

```bash
colcon test --packages-select lerobot_ros2_control --return-code-on-test-failure
```
