# LeRobot Setup

LeRobot Setup is a host-side terminal UI for the LeRobot Docker Compose
deployment. It manages Compose services through the Docker CLI. The TUI
does not communicate directly with ROS 2.

## Installation and startup

Use an APT-based Linux host with `sudo` and Python 3.10 or newer. For service
management, install Docker and its Compose plugin and make sure your user can
access the running Docker engine. Configure device mappings in
`docker/deploy/.env` using the [deployment guide](../../../docs/usage.md).

From the repository root, run:

```bash
./host/installation/install.sh
lerobot-setup
```

The installer creates a private virtual environment and installs the TUI in
editable mode. The launcher uses this checkout's deployment files from any
working directory. Keep the checkout in place and include `~/.local/bin` on
your `PATH`. File editing in Settings requires `nano`.

## Navigation

| Keys | Action |
| --- | --- |
| `1`, `2`, `5` | Open Dashboard, Services, or Settings. |
| `3`, `4` | Open the informational Robots and WiFi tabs. |
| `←` / `→`, `↑` / `↓` | In Services, change category or select a row. |
| `s`, `x`, `r`, `l` | Start, stop, restart, or view recent logs for a long-running service. |
| `e` | Run the selected one-shot service and view its output. |
| `Enter`, `Backspace` | In Settings, open a directory or file, or return to the parent directory. |
| `q` | Quit. In a log or error dialog, `q` or `Esc` closes the dialog. |

## Docker Compose services

The Dashboard shows host resource usage, Docker availability, service counts,
and container resource usage. In Services, select an entry to see its state
and command preview. Use **View Logs** for recent container output or
**View error details** after a failed operation.

Bringup, camera, teleoperation, MoveIt, and infrastructure services run in
containers. Camera discovery, servo scans, and torque tools can run as one-shot
commands. Use **Run Interactive** for calibration, serial port discovery, and
servo ID setup. One-shot and interactive runs use `--no-deps`, so start any
required services separately. Settings opens files in the deployment directory.

## Hardware precautions

A running container does not guarantee that the robot hardware or camera is
operational. Check device mappings and the service logs. On physical hardware,
bringup can enable torque, and teleoperation can move the follower during
alignment. Support the arm before calibration or torque release, and connect
only one servo at a time when assigning IDs.

**Stopping a container is not an emergency-stop mechanism.**
