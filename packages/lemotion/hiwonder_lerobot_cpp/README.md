# hiwonder_lerobot_cpp

## Overview

This package implements the generic `lerobot_cpp` robot interface for HiWonder
serial bus servos. It exports the `hiwonder_lerobot_cpp/Robot` plugin for both
SO-101 roles and provides tools for calibration, motion testing, and torque control.

## Usage

In a built and sourced workspace, use
[`hiwonder-find-port`](../hiwonder_servo_driver/README.md#usage) to
identify the adapter. Replace the example path with your adapter's persistent
`/dev/serial/by-id/` path when available.

```bash
port=/dev/serial/by-id/your-adapter-id
```

**Stop other processes controlling the arm before using these tools. Support
the arm before disabling torque. Keep the workspace clear and a hardware power
cutoff within reach before sending targets or enabling torque.** Torque control
over serial cannot serve as an emergency stop.

### `lerobot-calibrate`

```bash
lerobot-calibrate "$port" calibration.yaml --dof 6
```

Pass the port and output YAML path. The tool disables torque and prompts for
the raw position at each joint's URDF lower and upper limits. Move joints by
hand without forcing their mechanical stops. The final prompt saves the YAML
and overwrites any existing output file. Once torque is disabled, the tool
leaves it disabled even if calibration later fails.

### `lerobot-test-move`

```bash
lerobot-test-move --help
```

Help exits before accessing the bus. For hardware use, pass the port and
optionally `--dof`. Repeat `--motor ID:TICKS` for individual servos or use
`--all TICKS` for a group write. Targets are absolute raw ticks by default.
Use `--relative` for offsets from measured positions. Explicit targets must
resolve to 0–4095 ticks. Omitting both target options writes the measured
positions back as hold targets.

This example sends a one-tick relative target to servo 2 on a 6-DOF arm.
Check direction and clearance first.

```bash
lerobot-test-move "$port" --dof 6 --relative --motor 2:1
```

The tool writes raw targets without checking calibrated joint limits or
collisions. A write failure can leave earlier commands applied.

### `lerobot-torque-mode`

```bash
lerobot-torque-mode "$port" off
```

Pass the port and `off` to release torque or `on` to enable it. Enabling torque
can cause motion because the tool sets no position target first. It scans IDs
1–20 and requires responding IDs to be contiguous from 1. It accepts no DOF
option and can miss an absent last servo. Check the reported IDs against the
expected motor count.

## Architecture

[`lerobot_cpp`](../lerobot_cpp/) defines the robot interface. This package
implements it using the serial bus and servo operations from
[`hiwonder_servo_driver`](../hiwonder_servo_driver/).
[`lerobot_ros2_control`](../lerobot_ros2_control/) loads the plugin and maps
between calibrated ROS 2 joint values and raw servo values.

## Configuration

Calibration and motion testing default to 5 DOF. Pass `--dof 6` for a 6-DOF
arm. Both tools expect sequential IDs from 1, with the gripper at ID 6 for a
5-DOF arm or 7 for a 6-DOF arm. See the driver's
[ID setup](../hiwonder_servo_driver/README.md#assign-servo-ids) and
[bus scan](../hiwonder_servo_driver/README.md#usage) instructions.

For ROS 2 control, the adapter supplies the plugin's ordered IDs from the
calibration file. The plugin accepts a nonempty list of unique IDs from 0–253.
Use a calibration file matching the robot's hardware and control joints.
[Calibration guide and examples](../../lemodel/so101_description/config/README.md)

## Testing

From the built workspace root, run the package's hardware-free plugin and
configuration tests.

```bash
colcon test --packages-select hiwonder_lerobot_cpp --return-code-on-test-failure
```
