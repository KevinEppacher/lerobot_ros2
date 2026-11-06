# hiwonder_servo_driver

C++ driver for HiWonder serial bus servos with ROS 2.

The package provides a low-level C++ interface for communicating with HiWonder
bus servos over UART. It implements packet encoding, checksum validation,
register access, synchronous writes, and a higher-level servo interface.

The driver was developed and tested with the HiWonder servos used in the
HiWonder LeRobot SO-101, including the HX-30HM and HX-10HM servos.

## Features

- Serial communication with HiWonder bus servos
- Servo discovery using `PING`
- Register read and write operations
- 16-bit register access
- Broadcast `SYNC_WRITE` for controlling multiple servos
- Servo feedback including:
  - Position
  - Speed
  - Load
  - Voltage
  - Temperature
  - Current
- Torque control
- Servo ID configuration
- Baud-rate configuration
- Persistent NVS register configuration
- Command-line tools for setup and diagnostics
- Unit tests using GoogleTest

## Supported Hardware

The driver has been tested with:

- HiWonder HX-30HM
- HiWonder HX-10HM
- HiWonder LeRobot SO-101

The default communication baud rate is:

```text
1,000,000 baud
```

The driver communicates with the servo controller through a serial device such
as:

```text
/dev/ttyACM0
```

## Protocol

HiWonder servos use a binary UART protocol.

A request packet has the following structure:

```text
FF FF ID LENGTH INSTRUCTION PARAMETERS... CHECKSUM
```

A status packet returned by a servo has the following structure:

```text
FF FF ID LENGTH ERROR PARAMETERS... CHECKSUM
```

The checksum is calculated over all bytes from `ID` through the final parameter:

```text
CHECKSUM = ~(ID + LENGTH + INSTRUCTION/ERROR + PARAMETERS) & 0xFF
```

Implemented instructions include:

| Instruction | Value | Description |
|---|---:|---|
| PING | `0x01` | Check whether a servo responds |
| READ | `0x02` | Read registers |
| WRITE | `0x03` | Write registers |
| SYNC_WRITE | `0x83` | Write to multiple servos using broadcast |

The broadcast servo ID is:

```text
0xFE
```

## Architecture

The package is divided into three main layers:

```text
Servo
  |
  v
HiwonderBus
  |
  v
SerialPort
  |
  v
Linux serial device
```

### `SerialPort`

Provides the Linux UART interface using the POSIX serial API.

### `HiwonderBus`

Implements the HiWonder packet protocol, including:

- Packet construction
- Checksum calculation
- Status packet validation
- Register reads and writes
- Synchronous writes

### `Servo`

Provides a higher-level interface for interacting with individual servos and
their registers.

Register addresses are defined in:

```text
include/hiwonder_servo_driver/registers.hpp
```

## Build

The package requires ROS 2 and a C++20 compiler.

From the ROS 2 workspace:

```bash
colcon build --symlink-install --packages-select hiwonder_servo_driver
source install/setup.bash
```

## Tools

Command-line utilities for locating, inspecting and configuring the servo bus.
They assume the workspace is built and sourced. All tools use a baud rate of
1000000 and scan servo IDs 1-20.

For `lerobot-calibrate`, `lerobot-test-move` and `lerobot-torque-mode`, see the
`hiwonder_lerobot_cpp` package.

### `hiwonder-find-port`

Finds the serial port of the servo bus by detecting which `ttyACM*` / `ttyUSB*`
device disappears when the USB cable is unplugged.

```bash
hiwonder-find-port
```

The tool takes no arguments. It lists the available ports, asks you to
disconnect the USB cable and press Enter, and then prints the port that
disappeared. If a `/dev/serial/by-id/` link exists for it, the persistent path
is printed as well. It fails if no port or more than one port disappeared.
Reconnect the cable afterwards.

### `hiwonder-scan`

Pings every servo ID from 1 to 20 and prints firmware version, model ID,
configured ID, position, voltage and temperature for each servo found.

```bash
hiwonder-scan <port>
```

| Argument | Description | Default |
|---|---|---|
| `port` | Serial port of the servo bus | required |

Example:

```bash
hiwonder-scan /dev/ttyUSB0
```

The tool is read-only. It ends with `Found <n> servo(s).`

### `hiwonder-setup-motors`

Interactively assigns the servo IDs of an SO-101 arm, one servo at a time.

```bash
hiwonder-setup-motors <port> [--dof <5|6>]
```

| Argument | Description | Default |
|---|---|---|
| `port` | Serial port of the servo bus | required |
| `--dof <5\|6>` | Number of arm joints (the gripper is added) | `5` |

Examples:

```bash
hiwonder-setup-motors /dev/ttyUSB0
hiwonder-setup-motors /dev/ttyUSB0 --dof 6
```

ID assignment by `--dof`:

| ID | 5DOF | 6DOF |
|---:|---|---|
| 1 | `joint_1` | `joint_1` |
| 2 | `joint_2` | `joint_2` |
| 3 | `joint_3` | `joint_3` |
| 4 | `joint_4` | `joint_4` |
| 5 | `joint_5` | `joint_5` |
| 6 | `gripper` | `joint_6` |
| 7 | - | `gripper` |

Procedure, repeated for each joint in the order above:

1. Connect **only** the servo for the named joint to the bus.
2. Press Enter. The tool pings IDs 1-20 and requires exactly one servo to
   answer; zero or several responding servos abort the setup.
3. If the servo already has the target ID, nothing is changed. Otherwise its ID
   is rewritten to the target ID.
4. The new ID is verified with a ping. A failed change or verification aborts
   the setup.
5. Disconnect the servo and press Enter to continue with the next joint.

At the end the tool prints the configured IDs. The ID is written to the servo,
so only run the tool with a single servo on the bus.

## C++ API

Create a serial connection and bus:

```cpp
#include "hiwonder_servo_driver/hiwonder_bus.hpp"
#include "hiwonder_servo_driver/serial_port.hpp"
#include "hiwonder_servo_driver/servo.hpp"

hiwonder::SerialPort serial(
    "/dev/ttyACM0",
    1000000);

serial.open();

hiwonder::HiwonderBus bus(serial);
hiwonder::Servo servo(bus, 1);
```

Check whether the servo responds:

```cpp
if (bus.ping(1)) {
    // Servo is available.
}
```

Read a 16-bit register:

```cpp
uint16_t position = 0;

bus.readWord(
    1,
    hiwonder::reg::kCurrentPosition,
    position);
```

Write a 16-bit register:

```cpp
bus.writeWord(
    1,
    hiwonder::reg::kTargetPosition,
    2048);
```

## Synchronous Writes

`SYNC_WRITE` allows commands for multiple servos to be transmitted in a single
broadcast packet.

The payload is encoded as:

```text
ADDRESS DATA_LENGTH
ID_1 DATA...
ID_2 DATA...
...
```

Example:

```cpp
const std::array<uint8_t, 2> ids{
    1,
    2
};

const std::array<uint8_t, 4> data{
    0xE8,
    0x03,
    0xD0,
    0x07
};

bus.syncWrite(
    hiwonder::reg::kTargetPosition,
    2,
    ids,
    data);
```

Because `SYNC_WRITE` uses the broadcast ID, the servos do not return individual
status packets.

## Testing

Unit tests are implemented using GoogleTest.

Run the package tests with:

```bash
colcon test --packages-select hiwonder_servo_driver
colcon test-result --verbose
```

The tests cover:

- Checksum calculation
- Packet generation through the bus API
- `PING`
- Register reads and writes
- Little-endian 16-bit encoding and decoding
- Status packet validation
- Invalid checksums
- Servo error responses
- `SYNC_WRITE`
- Invalid input handling

Hardware-dependent tools are kept separate from the unit tests so the unit
tests can run without connected servos.

## Project Structure

```text
hiwonder_servo_driver/
├── include/
│   └── hiwonder_servo_driver/
│       ├── hiwonder_bus.hpp
│       ├── registers.hpp
│       ├── serial_port.hpp
│       └── servo.hpp
├── src/
│   ├── hiwonder_bus.cpp
│   ├── serial_port.cpp
│   └── servo.cpp
├── test/
│   ├── test_checksum.cpp
│   └── test_hiwonder_bus.cpp
├── tools/
│   ├── find_port.cpp
│   ├── scan.cpp
│   └── setup_motors.cpp
├── CMakeLists.txt
├── package.xml
└── README.md
```

## References

HiWonder servo SDK:

https://github.com/Hiwonder-official/hiwonder-servo-sdk

HiWonder SO-101:

https://github.com/Hiwonder-official/hiwonder-SoArm-101

HiWonder LeRobot:

https://github.com/Hiwonder-official/hiwonder-lerobot

## License

Copyright 2026 Kevin Eppacher

Licensed under the Apache License, Version 2.0.
See the repository `LICENSE` file for details.