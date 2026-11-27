# LeRobot TUI

LeRobot TUI is a host-side terminal UI for the LeRobot Docker Compose
deployment. It manages Compose services through the Docker CLI and inspects
the ROS graph through the host ROS 2 CLI.

## Installation and startup

Follow the [repository installation guide](../../../README.md#installation)
for the preferred Pixi workflow. Docker Engine and its Compose plugin are
required for service management. Configure device mappings in
`docker/deploy/.env` using the [deployment guide](../../../docs/usage.md).
File editing in Settings requires `nano`.

For a standalone installation into an existing Python 3.10 or newer
environment, run these commands from the repository root.

```bash
pip install -e host/src/lerobot_tui
lerobot
```

Set `LEROBOT_COMPOSE_FILE` to the absolute path of a deployment Compose
file when pointing the TUI at another checkout or using a wheel installation.

## Navigation

| Keys | Action |
| --- | --- |
| `1`–`6` | Open Dashboard, Services, Robots, ROS 2 Tools, WiFi, or Settings, respectively. |
| `←` / `→`, `↑` / `↓` | In Services, change category or select a row. |
| `s`, `x`, `r`, `l` | Start, stop, restart, or view recent logs for a long-running service. |
| `e` | Run the selected one-shot service and view its output. |
| `Enter`, `Backspace` | In Settings, open a directory or file, or return to the parent directory. |
| `q` | Quit. In an output or error dialog, `q` or `Esc` closes the dialog. |

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

## ROS 2 Tools

Use `pixi run tui` from `host/` to use the installed ROS 2 Jazzy CLI.
Discovery uses the active environment's ROS domain and DDS settings. If
`ros2` is unavailable, the tab explains how to activate it and Docker service
management remains available.

| Category | Read-only commands |
| --- | --- |
| Nodes | `ros2 node list`, `ros2 node info` |
| Topics | `ros2 topic list -t`, `ros2 topic info --verbose`, `ros2 topic echo`, `ros2 topic hz`, `ros2 interface show` |
| Services | `ros2 service list -t`, `ros2 interface show` |
| Actions | `ros2 action list -t`, `ros2 action info`, `ros2 interface show` |

Use `←` / `→` for categories, `↑` / `↓` for rows, and `Tab` to focus
controls such as the interface type selector for entities with multiple types.
Use `r` to refresh, `i` for Info, `e` for Echo, `h` for Hz, and `v` for
Interface. `Enter` on a row opens Info or, for services, Interface.
In a stream, `p` pauses or resumes display, `c` clears visible output, and
`Esc` or `q` closes the screen and stops the command.

## Hardware precautions

A running container does not guarantee that the robot hardware or camera is
operational. Check device mappings and the service logs. On physical hardware,
bringup can enable torque, and teleoperation can move the follower during
alignment. Support the arm before calibration or torque release, and connect
only one servo at a time when assigning IDs.

**Stopping a container is not an emergency-stop mechanism.**
