# lerobot_interfaces

## Overview

`lerobot_interfaces` defines the ROS 2 service type used to request control
mode changes in the LeRobot stack.

## Interfaces

[`SetControlMode.srv`](srv/SetControlMode.srv) accepts a `mode` of `IDLE` (0),
`TELEOP` (1), or `TRAJECTORY` (2). It returns a `success` flag and a diagnostic
`message`.

[`lerobot_control`](../lerobot_control/README.md) serves the relative name
`set_control_mode` and implements controller switching.
[`lerobot_teleop`](../lerobot_teleop/README.md) requests `TELEOP` for both arms.
In the mode manager, `IDLE` deactivates the managed controllers and leaves
motor torque unchanged.

## Usage

In a sourced workspace with the mode manager running, use
`ros2 service find lerobot_interfaces/srv/SetControlMode` to find the resolved
service name. With a follower in the standard namespace and its position
controller loaded and configured, request `TELEOP` with:

```bash
ros2 service call /follower/set_control_mode lerobot_interfaces/srv/SetControlMode "{mode: 1}"
```
