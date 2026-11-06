# hiwonder_lerobot_cpp

HiWonder backend for the generic `lerobot_cpp` robot interface.

The package provides the `hiwonder_lerobot_cpp/Leader` and
`hiwonder_lerobot_cpp/Follower` pluginlib plugins and command-line tools for
calibrating and testing SO-101 arms. The motor IDs are not hardcoded in the
plugins: they are passed through `lerobot::RobotConfig::motor_ids`, in order,
and must be non-empty, unique and in the range 0-253.

## Tools

The tools assume the workspace is built and sourced:

```bash
colcon build --symlink-install --packages-select hiwonder_lerobot_cpp
source install/setup.bash
```

All tools use a baud rate of 1000000 and expect the servo IDs to follow the
SO-101 convention (see `hiwonder-setup-motors` in the `hiwonder_servo_driver`
package):

| ID | 5DOF | 6DOF |
|---:|---|---|
| 1-5 | `joint_1` - `joint_5` | `joint_1` - `joint_5` |
| 6 | `gripper` | `joint_6` |
| 7 | - | `gripper` |

Find the serial port with `hiwonder-find-port`. Persistent
`/dev/serial/by-id/` paths are preferable to `/dev/ttyUSB*` names.

### `lerobot-calibrate`

Interactively records the raw servo positions that correspond to the URDF
lower and upper limit of every joint and writes them to a YAML file.

```bash
lerobot-calibrate <port> <calibration.yaml> [--dof <5|6>]
```

| Argument | Description | Default |
|---|---|---|
| `port` | Serial port of the servo bus | required |
| `calibration.yaml` | Output file, overwritten if it exists | required |
| `--dof <5\|6>` | Number of arm joints (the gripper is added) | `5` |

Examples:

```bash
lerobot-calibrate /dev/ttyUSB0 calibration.yaml
lerobot-calibrate /dev/ttyUSB0 calibration.yaml --dof 6
```

Workflow:

1. The tool connects to all servos (5DOF: IDs 1-6, 6DOF: IDs 1-7) and
   **disables torque**, so the arm can be moved by hand and will not hold its
   position.
2. For each joint in order (`joint_1` ... `joint_N`, then `gripper`), move the
   joint to its URDF **lower** limit and press Enter, then move it to its URDF
   **upper** limit and press Enter.
3. A joint whose lower and upper positions are identical aborts the
   calibration.
4. The recorded table is printed. Press Enter to save the file.

The output contains one entry per joint, so six entries for 5DOF and seven for
6DOF:

```yaml
joint_1:
  servo_id: 1
  lower_position: 618
  upper_position: 3363
...
gripper:
  servo_id: 6        # 7 for 6DOF
  lower_position: 1867
  upper_position: 3334
```

`lower_position` and `upper_position` may be in either order if the joint is
mounted inverted. `lerobot_ros2_control` reads `servo_id` from this file to
configure the motors, and the file must contain every joint of the selected
robot. A 5DOF file cannot be used with a 6DOF robot description.

Precautions:

- Torque stays disabled when the tool ends or aborts. Support the arm before
  starting, because it can fall under gravity.
- Move joints slowly and do not force them past their mechanical stops.
- Calibrate with the same DOF as the robot that will use the file.

### `lerobot-test-move`

Moves every motor by a small fixed offset to verify communication and motor
control.

```bash
lerobot-test-move <port> [--dof <5|6>]
```

| Argument | Description | Default |
|---|---|---|
| `port` | Serial port of the servo bus | required |
| `--dof <5\|6>` | Number of arm joints (the gripper is added) | `5` |

Examples:

```bash
lerobot-test-move /dev/ttyUSB0
lerobot-test-move /dev/ttyUSB0 --dof 6
```

`--dof` only selects the motor IDs (5DOF: 1-6, 6DOF: 1-7). The tool reads the
current raw position of every motor, prints `current -> target` for each, 
and sends a single command with a **-10 degree** offset (about -114 ticks). 
Targets below 0 are clamped to 0, so motors near the lower raw limit move 
less than 10 degrees and the other motors can still move. The offset is not 
configurable. If any resulting target exceeds 4095, the entire command is 
rejected without sending any motor targets.

Precautions:

- The motors move at once, without regard to joint limits or collisions.
  Keep the workspace clear and be ready to cut power.
- Check the direction of the offset first: -10 degrees in raw servo ticks can
  move a joint toward its mechanical limit.
- Use the matching `--dof`, otherwise the tool fails to connect or leaves
  a motor unmoved.

### `lerobot-torque-mode`

Enables or disables torque on all connected motors.

```bash
lerobot-torque-mode <port> <on|off>
```

| Argument | Description | Default |
|---|---|---|
| `port` | Serial port of the servo bus | required |
| `on` | Enable torque for position control | - |
| `off` | Disable torque for manual guiding | - |

There is no `--dof` argument. The tool discovers the motors itself by pinging
IDs 1-20 (the same range as `hiwonder-scan`) and prints the IDs found. It
exits with an error if:

- no motor answers, or
- the answering IDs are not contiguous from 1 (for example 1, 2, 4), which
  indicates a missing or unresponsive motor.

Examples:

```bash
lerobot-torque-mode /dev/ttyUSB0 off
lerobot-torque-mode /dev/ttyUSB0 on
```

Precautions:

- Disabling torque releases the joints: the arm falls under gravity unless it
  is supported.
- Enabling torque makes the motors hold their current position and resist
  motion. Keep hands clear of the arm.
- This tool is **not a safety-rated emergency stop**. It needs a working serial
  connection and a running host, and it does not cut motor power. Use a
  hardware power switch for emergency situations.
- Servos at unexpected IDs above the contiguous range are not controlled
  and are reported as an error.
