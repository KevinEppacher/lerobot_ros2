# SO-101 Setup and Usage

This guide covers hardware discovery, motor configuration, calibration, camera setup, and ROS 2 bringup for SO-101 leader and follower robotic arms using Docker Compose.

The setup utilities are designed to follow the original [Hugging Face LeRobot SO-101 setup procedure](https://huggingface.co/docs/lerobot/so101) as closely as possible. The familiar workflow is preserved while the tools run inside the LeRobot ROS2 container environment.

> [!IMPORTANT]
> Complete the hardware setup and calibration before enabling robot motion. Keep the workspace clear, provide adequate power, and be ready to disconnect power if a motor moves unexpectedly.

## Docker Compose Organization

The deployment is split into Compose files according to service responsibility:

| Compose file | Purpose | Examples |
| --- | --- | --- |
| `compose.yaml` | Robot and camera bringup | Leader, follower, wrist camera, front camera |
| `compose.tools.yaml` | Hardware discovery and motor setup | Find port, scan servos, configure motor IDs, list cameras |
| `compose.calibration.yaml` | Robot calibration | Leader and follower calibration |
| `compose.motion.yaml` | Motion control and teleoperation | Motor movement tests, leader-follower teleoperation |
| `compose.infrastructure.yaml` | Supporting infrastructure | Deployment-dependent services |

Unless otherwise noted, **run all Docker Compose commands from `docker/deploy/`**:

```bash
cd docker/deploy
```

For host installation and Docker prerequisites, see the [project README](../README.md) and [Docker installation guide](docker_install.md).

## 1. Configure the Environment

Create your local deployment configuration:

```bash
cp .env.example .env
```

The `.env` file holds host-specific device paths and deployment settings. You will fill in the robot and camera device paths after discovering them in the following steps.

> [!IMPORTANT]
> Do not commit your local `.env` file. It contains machine-specific configuration.

## 2. Identify Robot USB Ports

**Compose file:** `compose.tools.yaml`  
**Service:** `hiwonder-find-port`

Connect one SO-101 arm to the host and run:

```bash
docker compose -f compose.tools.yaml run --rm hiwonder-find-port
```

Follow the interactive prompts. The tool identifies the serial interface by asking you to disconnect the corresponding USB cable temporarily.

Example output (abbreviated):

```text
Finding all available ports for the Hiwonder servo bus.
Ports before disconnecting:
  /dev/ttyACM0

Disconnect the USB cable from the Hiwonder servo bus and press Enter.

The port of the Hiwonder servo bus is '/dev/ttyACM0'
Persistent device path: '/dev/serial/by-id/usb-1a86_USB_Single_Serial_5C82106754-if00'
Reconnect the USB cable
```

Repeat for the other arm. Then edit `.env` using the paths reported for **your** hardware:

```dotenv
LEADER_PORT=/dev/serial/by-id/usb-1a86_USB_Single_Serial_LEADER_ID-if00
FOLLOWER_PORT=/dev/serial/by-id/usb-1a86_USB_Single_Serial_FOLLOWER_ID-if00
```

Replace `LEADER_ID` and `FOLLOWER_ID` with the actual identifiers. Prefer `/dev/serial/by-id/` paths over `/dev/ttyUSB0` or `/dev/ttyACM0`: the latter can change when devices are reconnected or the host restarts.

You can inspect available persistent serial paths with:

```bash
ls -l /dev/serial/by-id/
```

## 3. Configure Servo Motor IDs

**Compose file:** `compose.tools.yaml`  
**Services:** `hiwonder-setup-motors-leader`, `hiwonder-setup-motors-follower`

The Hiwonder bus servos must have the correct IDs before normal robot operation. These interactive setup utilities are intended to mirror the motor configuration workflow of the original LeRobot SO-101 setup.

Configure the leader:

```bash
docker compose -f compose.tools.yaml run --rm hiwonder-setup-motors-leader
```

Configure the follower:

```bash
docker compose -f compose.tools.yaml run --rm hiwonder-setup-motors-follower
```

Follow the prompts and verify that you are configuring the intended arm.

> [!CAUTION]
> Incorrect servo IDs can prevent the robot from functioning correctly. Confirm the connected device and the intended robot configuration before changing motor settings.

## 4. Verify Servo Communication

**Compose file:** `compose.tools.yaml`  
**Services:** `hiwonder-scan-leader`, `hiwonder-scan-follower`

Scan the leader bus:

```bash
docker compose -f compose.tools.yaml run --rm hiwonder-scan-leader
```

Scan the follower bus:

```bash
docker compose -f compose.tools.yaml run --rm hiwonder-scan-follower
```

The scanner reports information such as servo ID, firmware version, position, voltage, and temperature. Example (abbreviated):

```text
Scanning Hiwonder servo bus
Port: /dev/hiwonder
Baud rate: 1000000

Servo found at ID 1
  Firmware: 3.11
  Model ID: 777
  Configured ID: 1
  Position: 1757
  Voltage: 12.3 V
  Temperature: 37 C

Servo found at ID 2
  Firmware: 3.11
  Model ID: 777
  Configured ID: 2
  Position: 1579
  Voltage: 12.5 V
  Temperature: 35 C

...
Found 7 servo(s).
```

The example is from a particular robot configuration. **The expected servo count depends on the selected model.** Verify that every configured joint and the gripper, where applicable, has a corresponding reachable servo.

## 5. Calibrate the Robots

**Compose file:** `compose.calibration.yaml`  
**Services:** `lerobot-calibrate-leader`, `lerobot-calibrate-follower`

Calibration records the servo positions corresponding to the joint limits defined in the robot description. Each joint is calibrated individually by moving it to its lower and upper limits and confirming the position.

> [!IMPORTANT]
> **Servo position range:** The Hiwonder servo position values used by this setup are expected to remain within **0–4095 ticks**. This is the servo's position representation, **not** a guarantee that every position is mechanically safe. Never force a joint beyond its physical limits. If the required range cannot be represented correctly, inspect the servo configuration and offset before continuing. Use the appropriate Hiwonder servo debugging software only if an offset adjustment is necessary ([Hiwonder Servo Studio](https://www.hiwonder.net/robot-debugging-software?utm_source)).

### 5.1 Calibrate the Leader

```bash
docker compose -f compose.calibration.yaml run --rm lerobot-calibrate-leader
```

The tool prompts you to move each joint to its URDF lower and upper limits. Example (abbreviated):

```text
LeRobot Calibration
====================

Connecting to robot...
Connected successfully.
Disabling motor torque...
Torque disabled.

Each joint will now be calibrated individually.
For each joint:
  1. Move it to the position corresponding to the URDF lower limit.
  2. Press ENTER.
  3. Move it to the position corresponding to the URDF upper limit.
  4. Press ENTER.

Joint 1/7: joint_1 (servo 1)
----------------------------------------
Move the joint to its URDF LOWER limit.
Press ENTER to record the position.
Recorded lower position: 458

Move the joint to its URDF UPPER limit.
Press ENTER to record the position.
Recorded upper position: 3089

...
Calibration file:
/config/calibration/6dof/leader_example_calibration.yaml

Press ENTER to save calibration.
Calibration saved successfully.
```

Some joints may have a decreasing tick value between the URDF lower and upper limits. Do not swap recorded values solely to make the tick values increase: verify the joint direction and physical limits instead.

### 5.2 Calibrate the Follower

```bash
docker compose -f compose.calibration.yaml run --rm lerobot-calibrate-follower
```

Follow the same guided procedure for the follower.

Calibration files are organized by robot configuration:

```text
config/calibration/
├── 5dof/
│   ├── leader_example_calibration.yaml
│   └── follower_example_calibration.yaml
└── 6dof/
    ├── leader_example_calibration.yaml
    └── follower_example_calibration.yaml
```

Select calibration files matching the configured robot model. The paths shown above are relative to `docker/deploy/`; the tool's output may show the corresponding path **inside** the container, such as `/config/calibration/6dof/leader_example_calibration.yaml`.

## 6. Test Robot Movement

**Compose file:** `compose.motion.yaml`  
**Services:** `lerobot-test-move-leader`, `lerobot-test-move-follower`

`lerobot-test-move` is primarily a hardware diagnostic utility for testing individual servo commands. It can also be invoked directly inside the development container for more targeted tests.

Its command-line interface supports the following options:

```text
Usage:
  lerobot-test-move <port> [--dof <5|6>]
  lerobot-test-move <port> [--dof <5|6>] --motor <id:ticks> [--motor <id:ticks> ...]
  lerobot-test-move <port> [--dof <5|6>] --all <ticks>

Options:
  --dof <5|6>         Number of arm joints (default: 5)
  --motor <id:ticks>  Set the target for a specific motor
  --all <ticks>       Set the same target for all motors
  --relative          Interpret ticks as relative offsets
  --help              Show this help message

Without --motor or --all, hold all motors at their current positions.
```

Examples for direct execution **inside the development container**:

```bash
lerobot-test-move /dev/ttyACM0 --dof 6
lerobot-test-move /dev/ttyACM0 --dof 6 --motor 3:2048
lerobot-test-move /dev/ttyACM0 --motor 1:1500 --motor 2:2500
lerobot-test-move /dev/ttyACM0 --relative --motor 2:-100
```

Use the actual device path exposed in your development environment.

For the Compose-defined tests, run:

**Leader:**

```bash
docker compose -f compose.motion.yaml run --rm lerobot-test-move-leader
```

**Follower:**

```bash
docker compose -f compose.motion.yaml run --rm lerobot-test-move-follower
```

> [!CAUTION]
> These commands can move the robot. Keep hands and objects away from moving joints, verify the commanded positions, and ensure that you can disconnect motor power immediately if necessary.

## 7. Set Up the Cameras

**Discovery Compose file:** `compose.tools.yaml`  
**Bringup Compose file:** `compose.yaml`

The documented camera hardware includes:

- **InnoMaker 720P USB 2.0 UVC camera**
- **Intel RealSense SR300**, used here as an **RGB camera**

### 7.1 Connect and Discover Cameras

Connect the cameras to the workstation or Raspberry Pi that will run the camera services.

On the host, list USB devices and video interfaces:

```bash
lsusb
ls -l /dev/video*
```

Alternatively, use the project camera discovery tool:

```bash
docker compose -f compose.tools.yaml run --rm lerobot-list-cameras
```

Example output (abbreviated from a Raspberry Pi setup):

```text
Available cameras:
  [1] Innomaker-U20CAM-720P  : Innoma
  [2] Intel(R) RealSense(TM) Camera S
  [3] bcm2835-codec-decode
  [4] bcm2835-isp

Video interfaces:

/dev/video0
  Camera: Innomaker-U20CAM-720P  : Innoma
  Type: RGB
  Formats: MJPG, YUYV
  Stable path: /dev/v4l/by-path/...-video-index0

/dev/video2
  Camera: Intel(R) RealSense(TM) Camera S
  Type: RGB
  Formats: YUYV
  Stable path: /dev/v4l/by-path/...-video-index0
```

A physical camera can expose more than one `/dev/video*` node. Raspberry Pi systems may also list internal codec or ISP interfaces; these are not necessarily external cameras.

### 7.2 Identify Stable Camera Paths

Inspect persistent identifiers:

```bash
ls -l /dev/v4l/by-id/
ls -l /dev/v4l/by-path/
```

Prefer stable identifiers over `/dev/video0` or `/dev/video2`, which may change after reconnecting devices or rebooting. If two cameras do not expose unique serial-number-based identifiers, `/dev/v4l/by-path/` can help distinguish them by their physical USB connection.

> [!NOTE]
> A `/dev/v4l/by-path/` identifier is tied to the USB connection topology. Moving a camera to another USB port may change its path.

### 7.3 Configure Camera Devices

Update the **camera-related entries already defined in `.env.example`** with the paths reported for your setup. Also verify that the camera services map the appropriate host devices into their containers.

The exact environment-variable names depend on the current deployment configuration; use `.env.example` as the authoritative reference rather than inventing new names.

### 7.4 Start Camera Bringup

**Follower wrist camera:**

```bash
docker compose -f compose.yaml up -d so101-follower-wrist-camera-bringup
```

**Follower front camera:**

```bash
docker compose -f compose.yaml up -d so101-follower-front-camera-bringup
```

Check container status and logs:

```bash
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs -f so101-follower-wrist-camera-bringup
```

### 7.5 Verify ROS 2 Image Topics

In an environment with ROS 2 installed and configured to communicate with the deployment:

```bash
ros2 topic list
ros2 topic info <camera_image_topic>
ros2 topic hz <camera_image_topic>
```

Replace `<camera_image_topic>` with the actual published topic. For visual inspection of compressed images, use a compatible ROS 2 image viewer or decompress/republish the stream as needed.

## 8. Start ROS 2 Robot Bringup

**Compose file:** `compose.yaml`

Once both robots are configured and calibrated, start the hardware interfaces.

**Leader:**

```bash
docker compose -f compose.yaml up -d so101-leader-bringup
```

**Follower:**

```bash
docker compose -f compose.yaml up -d so101-follower-bringup
```

The deployment maps the host-specific serial paths to fixed container device names:

| Robot | Host device | Container device |
| --- | --- | --- |
| Leader | `${LEADER_PORT}` | `/dev/so101_leader` |
| Follower | `${FOLLOWER_PORT}` | `/dev/so101_follower` |

This keeps the ROS 2 hardware configuration independent of the host's dynamically assigned USB device names.

### Leader-Follower Teleoperation

The teleoperation node enables real-time control of the follower robot using the leader's joint positions.

Before teleoperation begins, the follower smoothly aligns with the leader over a configurable duration. An optional low-pass filter reduces command jitter at the cost of responsiveness.

**Start teleoperation:**

```bash
docker compose -f compose.motion.yaml up -d lerobot-teleop
```

**Configuration:**

```yaml
leader_follower_teleop_node:
    ros__parameters:
        update_rate: 50.0
        leader:
            joint_state_topic: "/leader/joint_states"
            guiding_mode_service: "/leader/leader_so101/guiding_mode"
            control_mode_service: "/leader/set_control_mode"
            timeout: 0.2
        follower:
            joint_state_topic: "/follower/joint_states"
            command_topic: "/follower/position_controller/commands"
            control_mode_service: "/follower/set_control_mode"
            alignment_duration: 3.0
        low_pass_filter:
            enabled: true
            cutoff_frequency: 1.0
```

**Key parameters:**
- `update_rate`: Teleoperation frequency (Hz).
- `leader.timeout`: Maximum age of leader joint-state data (seconds).
- `alignment_duration`: Initial follower alignment duration (seconds).
- `cutoff_frequency`: Controls motion smoothness. Lower values reduce jitter but increase response delay.

> [!CAUTION]
> Ensure both robots are calibrated and their workspaces are clear before starting teleoperation.

## 9. Terminal User Interface

The same deployment can be managed through the LeRobot ROS2 terminal interface:

```bash
lerobot-setup
```

The TUI provides a dashboard for host and Docker resource monitoring, service management, container logs, and access to deployment configuration files. Hardware discovery, calibration, and diagnostics remain accessible through their respective Docker Compose services.

## Troubleshooting

### Serial Device Not Found

```bash
ls -l /dev/serial/by-id/
```

Confirm that the device exists, the cable is connected, and the `LEADER_PORT` or `FOLLOWER_PORT` entry matches the detected path.

### Servo Scan Fails or Finds Fewer Motors Than Expected

Check the selected serial port, power supply, servo IDs, bus wiring, and robot configuration. Rerun the appropriate `hiwonder-scan-*` service after correcting the issue.

### Calibration Produces Unexpected Values

Confirm that the correct arm and DOF configuration are selected. Check the joint's mechanical limits and servo direction. Do not force a joint beyond its safe range or assume that increasing ticks always correspond to increasing URDF joint positions.

### Camera Not Detected

```bash
lsusb
ls -l /dev/v4l/by-id/
ls -l /dev/v4l/by-path/
docker compose -f compose.tools.yaml run --rm lerobot-list-cameras
```

Verify the camera's physical connection, the configured stable device path, and the device mappings used by the camera container.

### Docker Service Fails to Start

```bash
docker compose -f compose.yaml ps
docker compose -f compose.yaml logs <service_name>
```

Use the Compose file containing the affected service. Replace `<service_name>` with the actual service name.

### Check Which Services a Compose File Defines

```bash
docker compose -f compose.tools.yaml config --services
docker compose -f compose.calibration.yaml config --services
docker compose -f compose.motion.yaml config --services
docker compose -f compose.yaml config --services
```

This is useful when service names or deployment configurations change.
