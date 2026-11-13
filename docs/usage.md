# Usage

This guide describes how to configure and run the SO-101 leader/follower setup using Docker Compose.

## 1. Find the USB device paths

Connect one SO-101 robot to the computer and run:

```bash
docker compose run --rm hiwonder-find-port
```

Follow the instructions and disconnect the USB cable when prompted.

The tool reports the persistent device path, for example:

```text
Persistent device path: '/dev/serial/by-id/usb-1a86_USB_Single_Serial_XXXXXXXX-if00'
```

Repeat this process for both the leader and follower robot.

Persistent `/dev/serial/by-id/` paths are used instead of `/dev/ttyACM0` or `/dev/ttyACM1` because the latter may change after reconnecting the devices or rebooting the system.

## 2. Configure the devices

Create a local `.env` file from the provided example:

```bash
cp .env.example .env
```

Set the persistent device paths of the leader and follower:

```env
LEADER_PORT=/dev/serial/by-id/usb-1a86_USB_Single_Serial_<leader-id>-if00
FOLLOWER_PORT=/dev/serial/by-id/usb-1a86_USB_Single_Serial_<follower-id>-if00
```

Docker Compose automatically reads the `.env` file when commands are executed from the `docs` directory.

The `.env` file contains machine-specific device paths and should not be committed to the repository.

## 3. Verify the servo buses

Scan the leader:

```bash
docker compose run --rm hiwonder-scan-leader
```

Scan the follower:

```bash
docker compose run --rm hiwonder-scan-follower
```

Both buses should report the connected servos.

## 4. Configure the motors

Configure the leader motors:

```bash
docker compose run --rm hiwonder-setup-motors-leader
```

Configure the follower motors:

```bash
docker compose run --rm hiwonder-setup-motors-follower
```

## 5. Calibrate the robots

Calibrate the leader:

```bash
docker compose run --rm lerobot-calibrate-leader
```

The calibration is written to:

```text
config/leader_example_calibration.yaml
```

Calibrate the follower:

```bash
docker compose run --rm lerobot-calibrate-follower
```

The calibration is written to:

```text
config/follower_example_calibration.yaml
```

## 6. Test the robots

Test the leader:

```bash
docker compose run --rm lerobot-test-move-leader
```

Test the follower:

```bash
docker compose run --rm lerobot-test-move-follower
```

## 7. Start the leader/follower setup

After both robots are configured and calibrated, start the complete setup:

```bash
docker compose up so101_bringup
```

The persistent host devices configured in `.env` are mapped to fixed device names inside the container:

| Robot | Host | Container |
| --- | --- | --- |
| Leader | `${LEADER_PORT}` | `/dev/so101_leader` |
| Follower | `${FOLLOWER_PORT}` | `/dev/so101_follower` |

This keeps the ROS 2 configuration independent of the host-specific USB device paths.

## Host setup interface

The host-side setup interface can be installed without installing ROS 2:

```bash
./host/install/install.sh
lerobot-setup
```

It manages services from `docker/deploy/compose.yaml` only and requires the
Docker CLI, its Compose plugin, and access to the Docker daemon. Use **1–5** to
open Dashboard, Services, Robots, WiFi, or Settings. In Services, select a row
and use the visible buttons or **S** (start), **X** (stop), **R** (restart),
**U** (pull/update image), or **L** (view the latest 100 log lines). Press
**Q** to quit. Updating a running service asks before recreating its container;
pulling an image for a stopped service leaves that service stopped.
