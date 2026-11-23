# hiwonder_servo_driver

## Overview

This Linux C++ driver communicates with HiWonder UART bus servos used in the
SO-101. It provides serial transport, register access, and tools for locating
the adapter, inspecting the bus, and assigning servo IDs.

## Usage

Build and source the workspace, then run:

```bash
hiwonder-find-port
```

Disconnect the USB adapter when prompted, press Enter, and reconnect it after
the tool identifies the port. Use the persistent `/dev/serial/by-id/` path if
one is reported. Replace the example path with your adapter's path.

```bash
port=/dev/serial/by-id/your-adapter-id
hiwonder-scan "$port"
```

The scan queries IDs 1–20 and prints available information for each responder.
Check the reported count. A scan with zero responders can exit successfully.

### Assign servo IDs

**Connect exactly one servo at a time.** The tool writes IDs to nonvolatile
servo storage. Discovery covers IDs 1–20, so physically isolate each servo
before proceeding.

```bash
hiwonder-setup-motors "$port" --dof 6
```

Connect the servo named in each prompt and press Enter. The tool requires one
response, writes the expected ID if needed, and verifies it with a ping.
Disconnect that servo before continuing to the next. If setup fails, rescan
the isolated servo before retrying. Earlier successful ID changes persist.

For calibration, motion testing, and torque control, see
[`hiwonder_lerobot_cpp`](../hiwonder_lerobot_cpp/README.md#usage).

## Architecture

- [`SerialPort`](include/hiwonder_servo_driver/serial_port.hpp) opens and owns
  the Linux serial device.
- [`HiwonderBus`](include/hiwonder_servo_driver/hiwonder_bus.hpp) handles packets,
  register access, and broadcast writes. A successful broadcast write confirms
  transmission. Individual servos do not acknowledge it.
- [`Servo`](include/hiwonder_servo_driver/servo.hpp) provides per-servo
  configuration and torque control. [`Motor`](include/hiwonder_servo_driver/motor.hpp)
  provides position commands and decoded state feedback.

## C++ API

Build consumers with C++20 and link the exported driver library. This example
takes a serial path as its only argument and pings servo ID 1.

```cpp
#include <exception>
#include <iostream>

#include "hiwonder_servo_driver/hiwonder_bus.hpp"
#include "hiwonder_servo_driver/serial_port.hpp"

int main(int argc, char * argv[])
{
  if (argc != 2) {
    std::cerr << "Pass the serial device path.\n";
    return 1;
  }

  try {
    hiwonder::SerialPort serial(argv[1]);
    serial.open();
    hiwonder::HiwonderBus bus(serial);
    if (bus.ping(1)) {
      return 0;
    }
    std::cerr << "No valid response from servo ID 1.\n";
  } catch (const std::exception & error) {
    std::cerr << error.what() << '\n';
  }
  return 1;
}
```

See [`registers.hpp`](include/hiwonder_servo_driver/registers.hpp) for supported
register addresses and the [HiWonder servo SDK](https://github.com/Hiwonder/hiwonder-servo-sdk)
for protocol and register documentation.

## Configuration

The scan and setup tools use 1,000,000 baud. Setup defaults to 5 DOF. Arm joint
IDs start at 1 in joint order, with the gripper at ID 6 for 5 DOF or ID 7 for
6 DOF. See the [calibration guide](../../lemodel/so101_description/config/README.md)
for joint-to-servo mapping and the upstream [HiWonder SO-101](https://github.com/Hiwonder/hiwonder-SoArm-101)
and [HiWonder LeRobot](https://github.com/Hiwonder/hiwonder-lerobot) projects.

## Testing

From the sourced ROS 2 workspace root, build the package and run its tests.
The unit tests use mock serial I/O or pure decoding and require no connected
servos.

```bash
colcon build --symlink-install --packages-select hiwonder_servo_driver
source install/setup.bash
colcon test --packages-select hiwonder_servo_driver --return-code-on-test-failure
colcon test-result --verbose
```
