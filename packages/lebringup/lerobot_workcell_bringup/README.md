# lerobot_workcell_bringup

ROS 2 bringup package for the SO-101 follower arm with the workcell robot description.

Reuses `lerobot_bringup` with `lerobot_workcell_description` (`urdf/workcell.urdf.xacro`).

## Usage

Launch the workcell:

```bash
ros2 launch lerobot_workcell_bringup workcell_bringup.launch.py \
    port:=/dev/serial/by-id/<device> \
    calibration_path:=/path/to/calibration.yaml
```

To enable RViz:

```bash
ros2 launch lerobot_workcell_bringup workcell_bringup.launch.py gui:=true
```

For available arguments:

```bash
ros2 launch lerobot_workcell_bringup workcell_bringup.launch.py --show-args
```

For controller configuration and general bringup behavior, see [`lerobot_bringup`](../lerobot_bringup/README.md).
