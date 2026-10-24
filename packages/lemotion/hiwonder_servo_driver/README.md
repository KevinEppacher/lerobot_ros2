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

Several command-line utilities are included for configuring and testing the
servos.

### Find serial port

```bash
hiwonder-find-port
```

Detects the serial device by asking the user to disconnect and reconnect the
USB adapter.

Example:

```text
/dev/ttyACM0
```

### Scan servo bus

```bash
hiwonder-scan
```

Scans the bus for connected servos and reads available servo information.

### Configure motor IDs

```bash
hiwonder-setup-motors
```

Configures the servo IDs used by the SO-101 arm.

The default configuration is:

| ID | Joint |
|---:|---|
| 1 | `joint_1` |
| 2 | `joint_2` |
| 3 | `joint_3` |
| 4 | `joint_4` |
| 5 | `joint_5` |
| 6 | `gripper` |

### Test servo movement

```bash
hiwonder-test-move
```

Sends a small movement command to the configured servos for verifying
communication and motor control.

### Torque control

```bash
hiwonder-torque-mode
```

Used for changing the torque state of the servos.

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
│   ├── setup_motors.cpp
│   ├── test_move.cpp
│   └── torque_mode.cpp
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