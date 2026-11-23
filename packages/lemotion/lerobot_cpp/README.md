# lerobot_cpp

## Overview

`lerobot_cpp` defines the header-only C++ interface for LeRobot hardware
backends. The contract is declared in
[`lerobot_cpp/robot.hpp`](include/lerobot_cpp/robot.hpp).

## Architecture

[`lerobot_ros2_control`](../lerobot_ros2_control/) loads a backend and converts
between raw hardware values and ROS 2 joint values.
[`hiwonder_lerobot_cpp`](../hiwonder_lerobot_cpp/) implements the interface for
HiWonder hardware using the serial bus operations in
[`hiwonder_servo_driver`](../hiwonder_servo_driver/).

## Plugin Interface

- **`RobotConfig`** carries the serial device path, baud rate (default
  1,000,000), and ordered motor IDs. The list length defines the configured
  motor count. Backends validate the settings for their hardware.
- **`JointState`** carries signed 16-bit position and velocity and unsigned
  16-bit current. Feedback is raw. Position I/O uses ticks, and the header
  defines no universal velocity or current scale. A backend used with the
  current ROS 2 adapter must provide raw values compatible with its
  [conversions](../lerobot_ros2_control/src/lerobot_system_hardware.cpp).
- **`Robot`** requires configuration, connection and disconnection,
  connection status, motor count, torque control, raw position reads and
  writes, target validation, and state feedback. Operations returning
  `bool` report failure with `false`. The status and motor-count queries are
  `noexcept`. The interface provides no thread-safety guarantee.

For the ROS 2 adapter, return one entry per configured motor in
`RobotConfig::motor_ids` order and interpret position commands in that same
order. Fill the read output vectors even when the caller passes them empty.
Allow cleanup after a failed configuration or connection.

## Plugin Integration

1. Declare dependencies on `lerobot_cpp` and `pluginlib`. Implement all pure
   virtual methods in a concrete class derived from `lerobot::Robot` with a
   public default constructor. See the
   [HiWonder backend header](../hiwonder_lerobot_cpp/include/hiwonder_lerobot_cpp/robot.hpp).
2. Register the shared library's class with `PLUGINLIB_EXPORT_CLASS`, using
   `lerobot::Robot` as the base type. Give the class a lookup name in the plugin
   XML and export that XML under the `lerobot_cpp` category. See the
   [HiWonder registration](../hiwonder_lerobot_cpp/hiwonder_lerobot_cpp_plugins.xml)
   and [CMake export](../hiwonder_lerobot_cpp/CMakeLists.txt).
3. Install the provider, source the workspace, and select its lookup name
   through the URDF hardware parameter `robot_plugin`. The adapter constructs
   the backend, supplies the serial settings and calibration-derived IDs in
   control-joint order, checks the motor count, then connects. It disconnects
   and releases the backend during cleanup.

Build the provider and consumer against the same version of the public header.
