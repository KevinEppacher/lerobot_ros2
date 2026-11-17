import asyncio
import json
import os
import shlex
import subprocess
from pathlib import Path

SERVICES = {
    "Bringup": (
        "so101-leader-follower-bringup",
        "so101-leader-bringup",
        "so101-follower-bringup",
        "so101-follower-wrist-camera-bringup",
        "so101-follower-front-camera-bringup",
    ),
    "Infrastructure": (
        "workstation_zenoh_bridge",
        "robot_zenoh_bridge",
    ),
    "Motion": (
        "so101-moveit-bringup",
        "lerobot-teleop",
        "lerobot-test-move-leader",
        "lerobot-test-move-follower",
    ),
    "Calibration": (
        "lerobot-calibrate-leader",
        "lerobot-calibrate-follower",
    ),
    "Tools": (
        "lerobot-list-cameras",
        "hiwonder-find-port",
        "hiwonder-scan-leader",
        "hiwonder-scan-follower",
        "hiwonder-setup-motors-leader",
        "hiwonder-setup-motors-follower",
        "lerobot-torque-mode-leader",
        "lerobot-torque-mode-follower",
    ),
}

INTERACTIVE_SERVICES = (
    "lerobot-calibrate-leader",
    "lerobot-calibrate-follower",
    "hiwonder-find-port",
    "hiwonder-setup-motors-leader",
    "hiwonder-setup-motors-follower",
)

ONESHOT_SERVICES = (
    "lerobot-test-move-leader",
    "lerobot-test-move-follower",
    "lerobot-list-cameras",
    "hiwonder-scan-leader",
    "hiwonder-scan-follower",
    "lerobot-torque-mode-leader",
    "lerobot-torque-mode-follower",
)

ALL_SERVICES = tuple(service for services in SERVICES.values() for service in services)

COMPOSE_FILES = {
    "Bringup": "compose.yaml",
    "Infrastructure": "compose.infrastructure.yaml",
    "Motion": "compose.motion.yaml",
    "Calibration": "compose.calibration.yaml",
    "Tools": "compose.tools.yaml",
}

RUN_ARGS = ("run", "--rm", "--no-deps")
INTERACTIVE_RUN_ARGS = (*RUN_ARGS, "--interactive", "--tty")


class DockerCompose:
    def __init__(self, compose_file: Path) -> None:
        self.compose_file = compose_file.resolve()
        self.directory = self.compose_file.parent

    def get_compose_file(self, service: str) -> str:
        for category, services in SERVICES.items():
            if service in services:
                return COMPOSE_FILES[category]

        raise ValueError(f"Unknown Docker service: {service}")

    def command(self, *args: str) -> list[str]:
        service = args[-1] if args and args[-1] in ALL_SERVICES else None

        if service is not None:
            files = (self.get_compose_file(service),)
        else:
            files = COMPOSE_FILES.values()

        command = ["docker", "compose"]

        for filename in files:
            command.extend(["-f", str(self.directory / filename)])

        return [*command, *args]

    def preview(self, *args: str) -> str:
        command = self.command(*args)

        for index, argument in enumerate(command):
            if argument == "-f" and index + 1 < len(command):
                command[index + 1] = Path(command[index + 1]).name

        return shlex.join(command)

    async def execute(self, *args: str) -> str:
        command = self.command(*args)

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.directory,
                env=os.environ.copy(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise RuntimeError(f"Cannot execute Docker: {exc}") from exc

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            message = stderr.decode(errors="replace").strip()
            raise RuntimeError(
                f"{shlex.join(command)}\n\n{message or stdout.decode(errors='replace').strip()}"
            )

        return stdout.decode(errors="replace").strip()

    async def start(self, service: str) -> None:
        await self.execute("up", "-d", service)

    async def stop(self, service: str) -> None:
        await self.execute("stop", service)

    async def restart(self, service: str) -> None:
        await self.execute("restart", service)

    async def logs(self, service: str) -> str:
        return await self.execute("logs", "--tail", "100", service)

    async def status(self) -> dict[str, str]:
        output = await self.execute(
            "ps",
            "--all",
            "--format",
            "json",
        )

        records = []

        if output:
            try:
                records = json.loads(output)
            except json.JSONDecodeError:
                records = [json.loads(line) for line in output.splitlines() if line.strip()]

        if isinstance(records, dict):
            records = [records]

        states = {
            record["Service"]: record["State"]
            for record in records
            if record.get("Service") in ALL_SERVICES
        }

        return {service: states.get(service, "not created") for service in ALL_SERVICES}

    async def run(self, service: str) -> str:
        return await self.execute(*RUN_ARGS, service)

    def run_interactive(self, service: str) -> int:
        command = self.command(*INTERACTIVE_RUN_ARGS, service)

        try:
            result = subprocess.run(
                command,
                cwd=self.directory,
                check=False,
            )
            exit_code = result.returncode

        except KeyboardInterrupt:
            exit_code = 130

        except OSError as exc:
            raise RuntimeError(f"Cannot execute Docker: {exc}") from exc

        print()
        print("-" * 50)
        print(f"Process exited with code {exit_code}.")

        try:
            input("Press Enter to return to LeRobot Setup...")
        except (KeyboardInterrupt, EOFError):
            pass

        return exit_code

    async def stats(self) -> list[dict[str, str]]:
        command = [
            "docker",
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self.directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise RuntimeError(f"Cannot execute Docker stats: {exc}") from exc

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(stderr.decode(errors="replace").strip())

        return [
            json.loads(line)
            for line in stdout.decode(errors="replace").splitlines()
            if line.strip()
        ]
