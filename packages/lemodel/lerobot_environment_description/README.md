# lerobot_environment_description

ROS 2 description package providing reusable URDF/Xacro models for the LeRobot environment.

## Models

- **Table:** Configurable dimensions (`width`, `depth`, `thickness`) and link prefix.
- **Environment:** Includes the table and attaches it to the `world` frame through a fixed joint.

## Usage

Generate the environment URDF:

```bash
ros2 run xacro xacro $(ros2 pkg prefix lerobot_environment_description --share)/urdf/<environment_file>.urdf.xacro
```

The table can also be included independently using the `table` Xacro macro.
