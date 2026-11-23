# lerobot_workcell_description

ROS 2 description package combining the SO-101 5-DOF follower arm with a workcell environment.

The workcell includes:
- An SO-101 follower arm with `ros2_control` configuration.
- A table defined by `lerobot_environment_description`.
- Fixed joints connecting the table and robot to the `world` frame.

## Usage

Visualize the workcell in RViz:

```bash
ros2 launch lerobot_workcell_description display.launch.py
```

Use `gui:=false` to disable RViz and the joint state publisher GUI.

For hardware bringup, see [`lerobot_workcell_bringup`](../../lebringup/lerobot_workcell_bringup/README.md).
