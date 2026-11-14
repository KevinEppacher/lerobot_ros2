# Usage

This guide describes how to configure and run the SO-101 leader/follower setup using Docker Compose.

## 1. Find the USB device paths

Connect one SO-101 robot to the computer and run:

```bash
docker compose run --rm --no-deps hiwonder-find-port
```

This tool is interactive: run it in a terminal (or an SSH session with a PTY) and follow
the instructions to disconnect the USB cable when prompted.

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

Run Compose commands from `docker/deploy`; Compose reads the `.env` file from that directory.

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

By default, the calibration is written to:

```text
config/calibration/5dof/leader_example_calibration.yaml
```

Calibrate the follower:

```bash
docker compose run --rm lerobot-calibrate-follower
```

By default, the calibration is written to:

```text
config/calibration/5dof/follower_example_calibration.yaml
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
docker compose up so101-leader-follower-bringup
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

It manages the deployment Compose project in `docker/deploy/` and requires the
Docker CLI, its Compose plugin, and access to the Docker daemon. The project is
assembled from `compose.yaml` and the infrastructure, motion, calibration, and
tools Compose files. Use **1–5** to
open Dashboard, Services, Robots, WiFi, or Settings. In Services, select a row
and use the visible buttons or **S** (start), **X** (stop), **R** (restart),
**U** (pull/update image), or **L** (view the latest 100 log lines). Press
**Q** to quit. Updating a running service asks before recreating its container;
pulling an image for a stopped service leaves that service stopped.

Use the category buttons above the service list to filter Bringup,
Infrastructure, Motion, Calibration, or Tools. Services are ordered with
running services first, then by name. A service defined in more than one
Compose file is assigned to the category of its last definition in merge order.
Select any service and choose **Info** to view its Compose source, image,
command, environment variables, Dockerfile (when defined), and documentation
reference.

One-shot tools expose **Configure** and **Run**; interactive setup and
calibration tools expose **Configure** and **Run Interactive**. Configuration is
kept for the current TUI session, with defaults read from the deployment
`.env`. Calibration tools accept a container path under
`/config/calibration/` or an absolute host path under
`docker/deploy/config/calibration/`; the resulting path is saved to `.env` and
used by calibration and bringup. Existing calibration output files require
confirmation before overwrite. Bringup checks that its selected calibration
input files exist.

One-shot output and exit status are shown in the TUI. Interactive tools
temporarily release the terminal and require a real TTY (including an SSH PTY).
After the tool exits, its output and exit status remain visible until **Enter**
returns to the TUI. Press **Ctrl+C** while the tool is running to cancel and
return to the TUI; cleanup can take several seconds. Hardware tools ask for
confirmation and warn when a managed service is using the configured device.
The TUI does not build images when starting services or running tools.
