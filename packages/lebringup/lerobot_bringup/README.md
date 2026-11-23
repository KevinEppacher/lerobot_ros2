# lerobot_bringup

## Overview

`lerobot_bringup` starts the ROS 2 hardware and control stack for physical 5-DOF
and 6-DOF SO-101 arms. It loads the robot description, starts the state publisher
and `ros2_control` controllers, and exposes control mode switching through
`lerobot_control`. It also provides optional RViz visualization and a launch
entry point for leader–follower teleoperation.

## Usage

Source the ROS 2 Jazzy workspace and identify the serial device and calibration
file for each arm. See the repository guides for
[hardware setup](../../../README.md#hardware-configuration) and
[robot calibration](../../../README.md#robot-calibration).

| Launch file | Use |
| --- | --- |
| [`so101_bringup.launch.py`](launch/so101_bringup.launch.py) | Start one leader or follower arm. |
| [`so101_leader_follower_bringup.launch.xml`](launch/so101_leader_follower_bringup.launch.xml) | Start both arms with independently selectable DOF. |
| [`so101_teleop.launch.xml`](launch/so101_teleop.launch.xml) | Start both arms with a shared DOF setting and enable leader–follower teleoperation. |

For example, start a 5-DOF follower using your serial device and calibration file.
Replace both example paths with your own.

```bash
ros2 launch lerobot_bringup so101_bringup.launch.py \
  robot_type:=follower dof:=5 port:=/dev/serial/by-id/your-device-id \
  calibration_path:=/path/to/follower_calibration.yaml
```

To list arguments for a launch file, run
`ros2 launch lerobot_bringup so101_teleop.launch.xml --show-args` with the
filename you want to inspect.

## Configuration

- **Hardware.** Set `port` and `calibration_path` for a single arm. For either
  paired launch, set `leader_port`, `follower_port`,
  `leader_calibration_path`, and `follower_calibration_path`. Use a persistent
  serial path where available.
- **Namespaces and RViz.** The single-arm launch defaults its namespace to
  `robot_type` and accepts a `namespace` override. The paired launches use
  `leader` and `follower`. The bundled
  [teleop configuration](../../lemotion/lerobot_teleop/config/leader_follower_config.yaml)
  uses those namespaces. Set `gui:=true` to start RViz. The paired launches open
  the leader view, and custom namespaces may require an adjusted RViz preset.
- **Controllers and robot description.** The selected DOF determines the
  [5-DOF](config/so101_5dof_controllers.yaml) or
  [6-DOF](config/so101_6dof_controllers.yaml) controller configuration.
  The single-arm launch accepts `description_package` and a package-relative
  `description_file` for a compatible Xacro, as used by
  [workcell bringup](../lerobot_workcell_bringup/launch/workcell_bringup.launch.py).
