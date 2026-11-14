import asyncio
import json
import os
import re
import select
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import termios
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

# The foreground group relays terminal interrupts to the TUI without signaling its process group.
_INTERACTIVE_EXEC = """
import os, signal, subprocess, sys
parent = os.getppid()
def interrupt(*_):
    if os.getppid() == parent:
        os.kill(parent, signal.SIGINT)
signal.signal(signal.SIGINT, interrupt)
os.setpgid(0, 0)
status = subprocess.call(sys.argv[1:])
sys.exit(128 - status if status < 0 else status)
"""


class DockerComposeError(RuntimeError):
    """Raised when a Docker Compose command cannot be completed."""


DEPLOY_COMPOSE_FILES = (
    ("compose.yaml", "Bringup"),
    ("compose.infrastructure.yaml", "Infrastructure"),
    ("compose.motion.yaml", "Motion"),
    ("compose.calibration.yaml", "Calibration"),
    ("compose.tools.yaml", "Tools"),
)


@dataclass(frozen=True, slots=True)
class ComposeService:
    name: str
    status: str
    state: str
    category: str = "Bringup"
    execution_type: str = "service"
    source_compose: str = "Not specified"
    image: str = "Not specified"
    command: str = "Not specified"
    environment_variables: tuple[str, ...] = ()
    dockerfile: str = "Not specified"
    documentation: str = "Not available"


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class ToolMetadata:
    execution_type: str
    environment_variables: tuple[str, ...] = ()
    hardware_variable: str | None = None
    hardware_access: bool = False
    may_overwrite_calibration: bool = False


TOOL_METADATA: dict[str, ToolMetadata] = {
    "lerobot-list-cameras": ToolMetadata("one-shot", hardware_access=True),
    "hiwonder-find-port": ToolMetadata("interactive", hardware_access=True),
    "hiwonder-scan-leader": ToolMetadata(
        "one-shot", ("LEADER_PORT",), "LEADER_PORT", hardware_access=True
    ),
    "hiwonder-scan-follower": ToolMetadata(
        "one-shot", ("FOLLOWER_PORT",), "FOLLOWER_PORT", hardware_access=True
    ),
    "lerobot-test-move-leader": ToolMetadata(
        "one-shot",
        ("LEADER_PORT", "LEADER_DOF"),
        "LEADER_PORT",
        hardware_access=True,
    ),
    "lerobot-test-move-follower": ToolMetadata(
        "one-shot",
        ("FOLLOWER_PORT", "FOLLOWER_DOF"),
        "FOLLOWER_PORT",
        hardware_access=True,
    ),
    "lerobot-torque-mode-leader": ToolMetadata(
        "one-shot",
        ("LEADER_PORT", "TORQUE_MODE"),
        "LEADER_PORT",
        hardware_access=True,
    ),
    "lerobot-torque-mode-follower": ToolMetadata(
        "one-shot",
        ("FOLLOWER_PORT", "TORQUE_MODE"),
        "FOLLOWER_PORT",
        hardware_access=True,
    ),
    "lerobot-calibrate-leader": ToolMetadata(
        "interactive",
        ("LEADER_PORT", "LEADER_DOF", "LEADER_CALIBRATION_FILE"),
        "LEADER_PORT",
        hardware_access=True,
        may_overwrite_calibration=True,
    ),
    "lerobot-calibrate-follower": ToolMetadata(
        "interactive",
        ("FOLLOWER_PORT", "FOLLOWER_DOF", "FOLLOWER_CALIBRATION_FILE"),
        "FOLLOWER_PORT",
        hardware_access=True,
        may_overwrite_calibration=True,
    ),
    "hiwonder-setup-motors-leader": ToolMetadata(
        "interactive",
        ("LEADER_PORT", "LEADER_DOF"),
        "LEADER_PORT",
        hardware_access=True,
    ),
    "hiwonder-setup-motors-follower": ToolMetadata(
        "interactive",
        ("FOLLOWER_PORT", "FOLLOWER_DOF"),
        "FOLLOWER_PORT",
        hardware_access=True,
    ),
}

BRINGUP_CALIBRATION_VARIABLES: dict[str, tuple[str, ...]] = {
    "so101-leader-follower-bringup": (
        "LEADER_CALIBRATION_FILE",
        "FOLLOWER_CALIBRATION_FILE",
    ),
    "so101-leader-bringup": ("LEADER_CALIBRATION_FILE",),
    "so101-follower-bringup": ("FOLLOWER_CALIBRATION_FILE",),
}


class DockerComposeManager:
    def __init__(
        self,
        compose_file: Path,
        project_name: str | None = None,
    ) -> None:
        self._compose_file = compose_file.resolve()
        self._project_name = project_name

        if (
            self._compose_file.name != "compose.yaml"
            or self._compose_file.parent.name != "deploy"
            or self._compose_file.parent.parent.name != "docker"
        ):
            raise ValueError("The TUI only manages the deployment files in docker/deploy.")

        self._compose_files = tuple(
            self._compose_file.parent / filename for filename, _ in DEPLOY_COMPOSE_FILES
        )
        missing_files = [path for path in self._compose_files if not path.is_file()]
        if missing_files:
            missing = ", ".join(str(path) for path in missing_files)
            raise FileNotFoundError(f"Deployment Compose file(s) not found: {missing}")

        self._catalog: list[ComposeService] | None = None
        self._service_devices: dict[str, set[str]] = {}
        self._explicitly_stopped: set[str] = set()
        self._dotenv = self._read_dotenv(self._compose_file.parent / ".env")
        self._compose_overrides: dict[str, str] = {}

    @property
    def calibration_root(self) -> Path:
        return (self._compose_file.parent / "config" / "calibration").resolve()

    @staticmethod
    def default_calibration_file(variable: str, dof: str) -> str:
        if variable not in {"LEADER_CALIBRATION_FILE", "FOLLOWER_CALIBRATION_FILE"}:
            raise ValueError(f"Unsupported calibration variable: {variable}")
        if dof not in {"5", "6"}:
            raise ValueError(f"Unsupported robot DOF: {dof}")
        robot = variable.removesuffix("_CALIBRATION_FILE").lower()
        return f"/config/calibration/{dof}dof/{robot}_example_calibration.yaml"

    def resolve_calibration_path(self, value: str) -> Path:
        if not value or "\0" in value or "\n" in value or "\r" in value:
            raise ValueError("Enter a calibration YAML path.")
        if value.startswith("/config/calibration/"):
            relative = PurePosixPath(value).relative_to("/config/calibration")
            if ".." in relative.parts:
                raise ValueError("Calibration paths cannot contain parent-directory segments.")
            candidate = self.calibration_root.joinpath(*relative.parts)
        else:
            candidate = Path(value)
            if not candidate.is_absolute():
                raise ValueError("Use a /config/calibration path or an absolute host path.")

        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.calibration_root)
        except ValueError as exc:
            raise ValueError(
                "Calibration files must remain inside docker/deploy/config/calibration."
            ) from exc
        if resolved.suffix.lower() not in {".yaml", ".yml"}:
            raise ValueError("Calibration output files must use a .yaml or .yml extension.")
        return resolved

    def calibration_container_path(self, value: str | Path) -> str:
        host_path = self.resolve_calibration_path(str(value))
        relative = host_path.relative_to(self.calibration_root)
        return PurePosixPath("/config/calibration", *relative.parts).as_posix()

    def prepare_calibration_output(self, value: str) -> tuple[str, Path]:
        container_path = self.calibration_container_path(value)
        host_path = self.resolve_calibration_path(container_path)
        host_path.parent.mkdir(parents=True, exist_ok=True)
        host_path = self.resolve_calibration_path(container_path)
        if not host_path.parent.is_dir() or not os.access(host_path.parent, os.W_OK | os.X_OK):
            raise OSError(f"Calibration directory is not writable: {host_path.parent}")
        if host_path.exists() and (not host_path.is_file() or not os.access(host_path, os.W_OK)):
            raise OSError(f"Calibration output is not a writable regular file: {host_path}")
        return container_path, host_path

    def validate_calibration_input(self, value: str) -> Path:
        host_path = self.resolve_calibration_path(value)
        if not host_path.is_file() or not os.access(host_path, os.R_OK):
            raise ValueError(f"Calibration file does not exist or is unreadable: {host_path}")
        return host_path

    def calibration_files(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = []
        if not self.calibration_root.is_dir():
            return options
        for path in sorted(self.calibration_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".yaml", ".yml"}:
                continue
            try:
                container_path = self.calibration_container_path(path)
            except ValueError:
                continue
            options.append((container_path, container_path))
        return options

    def calibration_directories(self) -> list[tuple[str, str]]:
        if not self.calibration_root.is_dir():
            return []
        options = [("/config/calibration", "/config/calibration")]
        for path in sorted(self.calibration_root.rglob("*")):
            if not path.is_dir():
                continue
            try:
                container_path = self.calibration_container_path(path / "placeholder.yaml")
            except ValueError:
                continue
            directory = str(PurePosixPath(container_path).parent)
            options.append((directory, directory))
        return options

    def save_calibration_file(self, variable: str, value: str) -> tuple[str, Path]:
        if variable not in {"LEADER_CALIBRATION_FILE", "FOLLOWER_CALIBRATION_FILE"}:
            raise ValueError(f"Unsupported calibration variable: {variable}")
        container_path, host_path = self.prepare_calibration_output(value)
        self._save_dotenv_value(variable, container_path)
        self._dotenv[variable] = container_path
        self._compose_overrides[variable] = container_path
        return container_path, host_path

    def _save_dotenv_value(self, key: str, value: str) -> None:
        path = self._compose_file.parent / ".env"
        original = path.read_text() if path.exists() else ""
        encoded = "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
        replacement = f"{key}={encoded}"
        lines = original.splitlines(keepends=True)
        updated: list[str] = []
        found = False
        for line in lines:
            if re.match(rf"^\s*{re.escape(key)}\s*=", line):
                newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                updated.append(replacement + newline)
                found = True
            else:
                updated.append(line)
        if not found:
            if updated and not updated[-1].endswith(("\n", "\r")):
                updated[-1] += "\n"
            updated.append(replacement + "\n")

        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=".env.",
                delete=False,
            ) as temporary:
                temporary_name = temporary.name
                temporary.writelines(updated)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.chmod(temporary_name, mode)
            os.replace(temporary_name, path)
        except OSError:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)
            raise

    @staticmethod
    def _read_dotenv(path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        if not path.is_file():
            return values

        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key:
                values[key] = value.strip("\"'")
        return values

    def environment_value(self, key: str) -> str:
        return self._compose_overrides.get(key, os.environ.get(key, self._dotenv.get(key, "")))

    def metadata_for(self, service: str) -> ToolMetadata:
        return TOOL_METADATA.get(service, ToolMetadata("service"))

    def _command(
        self,
        *args: str,
        compose_files: tuple[Path, ...] | None = None,
    ) -> list[str]:
        command = ["docker", "compose"]
        files = self._compose_files if compose_files is None else compose_files
        for compose_file in files:
            command.extend(["-f", str(compose_file)])
        if self._project_name is not None:
            command.extend(["-p", self._project_name])
        command.extend(args)
        return command

    async def _spawn(
        self,
        *args: str,
        environment: dict[str, str] | None = None,
        capture_output: bool = True,
        compose_files: tuple[Path, ...] | None = None,
    ) -> asyncio.subprocess.Process:
        try:
            command = self._command(*args, compose_files=compose_files)
            process_environment = os.environ.copy()
            process_environment.update(self._compose_overrides)
            if environment is not None:
                process_environment.update(environment)
            return await asyncio.create_subprocess_exec(
                *command,
                cwd=self._compose_file.parent,
                env=process_environment,
                stdin=(asyncio.subprocess.PIPE if capture_output else None),
                stdout=(asyncio.subprocess.PIPE if capture_output else None),
                stderr=(asyncio.subprocess.PIPE if capture_output else None),
            )
        except FileNotFoundError as exc:
            raise DockerComposeError(
                "Docker CLI not found. Install Docker with the Compose plugin."
            ) from exc
        except PermissionError as exc:
            raise DockerComposeError(f"Cannot execute Docker CLI: {exc}") from exc
        except OSError as exc:
            raise DockerComposeError(f"Could not start Docker CLI: {exc}") from exc

    @staticmethod
    async def _terminate(process: asyncio.subprocess.Process) -> None:
        if process.returncode is not None:
            return
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=1)
        except TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()

    async def _execute(
        self,
        *args: str,
        environment: dict[str, str] | None = None,
        compose_files: tuple[Path, ...] | None = None,
    ) -> str:
        process = await self._spawn(
            *args,
            environment=environment,
            compose_files=compose_files,
        )
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            await self._terminate(process)
            raise

        if process.returncode != 0:
            details = stderr.decode(errors="replace").strip()
            if not details:
                details = stdout.decode(errors="replace").strip()
            if not details:
                details = f"Docker Compose exited with status {process.returncode}."
            raise DockerComposeError(details)

        return stdout.decode(errors="replace").strip()

    async def get_catalog(self) -> list[ComposeService]:
        if self._catalog is not None:
            return list(self._catalog)

        output = await self._execute("--profile", "*", "config", "--format", "json")
        try:
            compose_config: Any = json.loads(output)
        except json.JSONDecodeError as exc:
            raise DockerComposeError("Docker Compose returned invalid configuration JSON.") from exc
        service_configs = (
            compose_config.get("services") if isinstance(compose_config, dict) else None
        )
        if not isinstance(service_configs, dict):
            raise DockerComposeError("Docker Compose configuration has no services mapping.")

        categories: dict[str, str] = {}
        definitions: dict[str, tuple[str, dict[str, Any]]] = {}
        for filename, category in DEPLOY_COMPOSE_FILES:
            file_output = await self._execute(
                "-f",
                str(self._compose_file.parent / filename),
                "--profile",
                "*",
                "config",
                "--no-interpolate",
                "--format",
                "json",
                compose_files=(self._compose_file.parent / filename,),
            )
            try:
                file_config: Any = json.loads(file_output)
            except json.JSONDecodeError as exc:
                raise DockerComposeError(
                    f"Docker Compose returned invalid configuration for {filename}."
                ) from exc
            file_services = file_config.get("services") if isinstance(file_config, dict) else None
            if not isinstance(file_services, dict):
                raise DockerComposeError(
                    f"Docker Compose configuration {filename} has no services mapping."
                )
            for name, service_config in file_services.items():
                if isinstance(name, str) and isinstance(service_config, dict):
                    # The last definition owns the category, matching Compose merge order.
                    categories[name] = category
                    definitions[name] = (filename, service_config)

        self._service_devices = {}
        catalog: list[ComposeService] = []
        for name, config in service_configs.items():
            if not isinstance(name, str) or not isinstance(config, dict):
                continue
            metadata = self.metadata_for(name)
            source_filename, source_config = definitions.get(name, ("", {}))
            command = config.get("command")
            command_text = (
                shlex.join([str(argument) for argument in command])
                if isinstance(command, list)
                else str(command)
                if isinstance(command, str)
                else "Not specified"
            )
            variable_references = set(
                re.findall(r"\$\{([A-Z_][A-Z0-9_]*)", json.dumps(source_config))
            )
            environment = source_config.get("environment", {})
            if isinstance(environment, dict):
                variable_references.update(str(key) for key in environment)
            elif isinstance(environment, list):
                variable_references.update(
                    str(item).split("=", 1)[0] for item in environment if isinstance(item, str)
                )
            variable_references.update(metadata.environment_variables)
            build = source_config.get("build")
            dockerfile = "Not specified"
            if isinstance(build, str):
                dockerfile = str(Path("docker/deploy") / build / "Dockerfile")
            elif isinstance(build, dict):
                context = str(build.get("context", "."))
                filename = str(build.get("dockerfile", "Dockerfile"))
                dockerfile = str(Path("docker/deploy") / context / filename)
            documentation = self._documentation_reference(name)
            self._service_devices[name] = self._device_sources(config)
            catalog.append(
                ComposeService(
                    name=name,
                    status="Not created",
                    state="not created",
                    category=categories.get(name, "Bringup"),
                    execution_type=metadata.execution_type,
                    source_compose=(
                        f"docker/deploy/{source_filename}" if source_filename else "Not specified"
                    ),
                    image=str(config.get("image", "Not specified")),
                    command=command_text,
                    environment_variables=tuple(sorted(variable_references)),
                    dockerfile=dockerfile,
                    documentation=documentation,
                )
            )

        self._catalog = sorted(catalog, key=lambda service: service.name)
        return list(self._catalog)

    def _documentation_reference(self, service: str) -> str:
        repository_root = self._compose_file.parent.parent.parent
        candidates = (
            Path("docs/usage.md"),
            Path("docs/docker_usage.md"),
            Path("README.md"),
        )
        for relative in candidates:
            path = repository_root / relative
            try:
                if path.is_file() and service in path.read_text(encoding="utf-8"):
                    return relative.as_posix()
            except OSError:
                continue
        return "Not available"

    @staticmethod
    def _device_sources(service_config: dict[str, Any]) -> set[str]:
        sources: set[str] = set()
        for device in service_config.get("devices", []):
            source = device.get("source") if isinstance(device, dict) else None
            if isinstance(source, str):
                sources.add(os.path.realpath(source))
        return sources

    async def get_services(self) -> list[str]:
        return [service.name for service in await self.get_catalog()]

    async def get_status(self) -> list[ComposeService]:
        output = await self._execute("ps", "--all", "--format", "json")
        if not output:
            return []

        try:
            parsed: Any = json.loads(output)
            records = parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            try:
                records = [json.loads(line) for line in output.splitlines() if line.strip()]
            except json.JSONDecodeError as exc:
                raise DockerComposeError(
                    "Docker Compose returned invalid service status JSON."
                ) from exc

        service_records: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("Service"), str):
                raise DockerComposeError(
                    "Docker Compose returned an unexpected service status record."
                )
            service_records.setdefault(record["Service"], []).append(record)

        services: list[ComposeService] = []
        for name, records_for_service in sorted(service_records.items()):
            states = sorted({str(record.get("State", "unknown")) for record in records_for_service})
            statuses = sorted(
                {str(record.get("Status", "Unknown")) for record in records_for_service}
            )
            state = (
                "running" if "running" in states else states[0] if len(states) == 1 else "partial"
            )
            if name in self._explicitly_stopped and state == "exited":
                state = "stopped"
            services.append(
                ComposeService(
                    name=name,
                    state=state,
                    status="; ".join(statuses),
                )
            )
        return services

    async def active_services_using_device(self, device: str) -> list[str]:
        if self._catalog is None:
            await self.get_catalog()
        target = os.path.realpath(device)
        users = [name for name, sources in self._service_devices.items() if target in sources]
        if not users:
            return []

        active = {service.name for service in await self.get_status() if service.state == "running"}
        return sorted(active.intersection(users))

    async def start(self, service: str) -> None:
        self._validate_bringup_calibrations(service)
        await self._execute("up", "-d", "--no-build", service)
        self._explicitly_stopped.discard(service)

    async def stop(self, service: str) -> None:
        await self._execute("stop", service)
        self._explicitly_stopped.add(service)

    async def restart(self, service: str) -> None:
        self._validate_bringup_calibrations(service)
        await self._execute("restart", service)
        self._explicitly_stopped.discard(service)

    async def logs(self, service: str) -> str:
        return await self._execute("logs", "--tail", "100", service)

    async def pull(self, service: str) -> None:
        await self._execute("pull", service)

    async def recreate(self, service: str) -> None:
        self._validate_bringup_calibrations(service)
        await self._execute(
            "up",
            "-d",
            "--no-build",
            "--no-deps",
            "--force-recreate",
            service,
        )

    def _validate_bringup_calibrations(self, service: str) -> None:
        variables = BRINGUP_CALIBRATION_VARIABLES.get(service, ())
        for variable in variables:
            dof_variable = variable.removesuffix("_CALIBRATION_FILE") + "_DOF"
            dof = self.environment_value(dof_variable) or "5"
            path = self.environment_value(variable) or self.default_calibration_file(variable, dof)
            self.validate_calibration_input(path)

    async def run_tool(
        self,
        service: str,
        environment: dict[str, str],
    ) -> ToolExecutionResult:
        process = await self._spawn(
            "run",
            "--rm",
            "--no-deps",
            service,
            environment={**os.environ, **environment},
        )
        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            await self._terminate(process)
            raise
        if process.returncode is None:
            raise DockerComposeError("Docker Compose tool process ended without an exit status.")
        return ToolExecutionResult(
            exit_code=process.returncode,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )

    def run_interactive_tool(
        self,
        service: str,
        environment: dict[str, str],
    ) -> int | None:
        terminal = sys.stdin.fileno()
        foreground = os.tcgetpgrp(terminal)
        if foreground != os.getpgrp():
            raise DockerComposeError("Interactive tools require a foreground terminal.")
        attributes = termios.tcgetattr(terminal)
        interrupted = False

        def on_interrupt(*_: object) -> None:
            nonlocal interrupted
            interrupted = True

        previous_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, on_interrupt)
        name = f"lerobot-tui-{uuid4().hex}"
        process: subprocess.Popen[bytes] | None = None
        cancelled = False
        try:
            try:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        _INTERACTIVE_EXEC,
                        *self._command(
                            "run",
                            "--rm",
                            "--no-deps",
                            "--interactive",
                            "--name",
                            name,
                            service,
                        ),
                    ],
                    cwd=self._compose_file.parent,
                    env={**os.environ, **self._compose_overrides, **environment},
                    stdin=None,
                    stdout=None,
                    stderr=None,
                )
            except OSError as exc:
                raise DockerComposeError(f"Could not start Docker CLI: {exc}") from exc

            for _ in range(500):
                if process.poll() is not None:
                    break
                try:
                    if os.getpgid(process.pid) == process.pid:
                        break
                except ProcessLookupError:
                    process.wait()
                    break
                time.sleep(0.01)
            else:
                raise DockerComposeError("Timed out creating the interactive process group.")
            if process.poll() is None:
                self._set_terminal_foreground(terminal, process.pid)
                try:
                    os.killpg(process.pid, signal.SIGCONT)
                except ProcessLookupError:
                    process.wait()

            while process.poll() is None:
                if interrupted:
                    cancelled = True
                    self._stop_interactive_process(process)
                    break
                self._keep_terminal_interruptible(terminal)
                try:
                    process.wait(timeout=0.02)
                except subprocess.TimeoutExpired:
                    continue
            exit_code = process.wait()
            cancelled = cancelled or interrupted
            if cancelled:
                return None

            self._restore_interactive_terminal(terminal, foreground, attributes)
            self._show_interactive_result(service, exit_code)
            if not self._wait_for_interactive_confirmation(terminal, lambda: interrupted):
                cancelled = True
                return None
            return exit_code
        except KeyboardInterrupt:
            cancelled = True
            return None
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            try:
                try:
                    if process is not None and process.poll() is None:
                        cancelled = True
                        self._stop_interactive_process(process)
                finally:
                    if process is not None and cancelled:
                        try:
                            self._finish_interactive_group(process.pid)
                            if process.poll() is None:
                                process.wait(timeout=2)
                        finally:
                            self._remove_interactive_container(name)
            finally:
                try:
                    self._restore_interactive_terminal(terminal, foreground, attributes)
                finally:
                    signal.signal(signal.SIGINT, previous_handler)

    @classmethod
    def _restore_interactive_terminal(
        cls,
        terminal: int,
        foreground: int,
        attributes: list[Any],
    ) -> None:
        cls._set_terminal_foreground(terminal, foreground)
        termios.tcsetattr(terminal, termios.TCSANOW, attributes)

    @staticmethod
    def _show_interactive_result(service: str, exit_code: int) -> None:
        result = "SUCCEEDED" if exit_code == 0 else "FAILED"
        summary = (
            "\n" + "-" * 52 + f"\nTool: {service}\nStatus: {result}\nExit code: {exit_code}\n\n"
            "The tool's stdout and stderr are shown above.\n"
            "Press Enter to return to LeRobot Setup. (Ctrl+C to return)\n"
        )
        sys.stdout.write(summary)
        sys.stdout.flush()

    @staticmethod
    def _wait_for_interactive_confirmation(
        terminal: int,
        interrupted: Callable[[], bool],
    ) -> bool:
        termios.tcflush(terminal, termios.TCIFLUSH)
        while not interrupted():
            readable, _, _ = select.select([terminal], [], [], 0.1)
            if readable:
                character = os.read(terminal, 1)
                if not character:
                    return False
                if character in (b"\n", b"\r"):
                    return True
        return False

    @staticmethod
    def _set_terminal_foreground(terminal: int, group: int) -> None:
        previous = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        try:
            os.tcsetpgrp(terminal, group)
        finally:
            signal.signal(signal.SIGTTOU, previous)

    @staticmethod
    def _keep_terminal_interruptible(terminal: int) -> None:
        attributes = termios.tcgetattr(terminal)
        if not attributes[3] & termios.ISIG:
            # Compose uses raw mode; retain its input behavior except for Ctrl+C.
            attributes[3] |= termios.ISIG
            disabled = os.fpathconf(terminal, "PC_VDISABLE")
            attributes[6][termios.VQUIT] = bytes([disabled])
            attributes[6][termios.VSUSP] = bytes([disabled])
            previous = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
            try:
                termios.tcsetattr(terminal, termios.TCSANOW, attributes)
            finally:
                signal.signal(signal.SIGTTOU, previous)

    @staticmethod
    def _stop_interactive_process(process: subprocess.Popen[bytes]) -> None:
        for sig, timeout in ((signal.SIGINT, 5), (signal.SIGTERM, 2), (signal.SIGKILL, 2)):
            if process.poll() is not None:
                return
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                try:
                    process.send_signal(sig)
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=timeout)
                return
            except subprocess.TimeoutExpired:
                continue
        raise DockerComposeError("The interactive Docker process did not terminate.")

    @staticmethod
    def _finish_interactive_group(group: int) -> None:
        deadline = time.monotonic() + 1
        while True:
            try:
                os.killpg(group, 0)
            except ProcessLookupError:
                return
            if time.monotonic() >= deadline:
                try:
                    os.killpg(group, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                return
            time.sleep(0.05)

    def _remove_interactive_container(self, name: str) -> None:
        try:
            result = subprocess.run(
                ["docker", "rm", "-f", name],
                cwd=self._compose_file.parent,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DockerComposeError(f"Timed out removing interactive container {name}.") from exc
        except OSError as exc:
            raise DockerComposeError(
                f"Could not remove interactive container {name}: {exc}"
            ) from exc
        if result.returncode != 0 and b"No such container" not in result.stderr:
            raise DockerComposeError(
                f"Could not remove interactive container {name}: "
                f"{result.stderr.decode(errors='replace').strip()}"
            )
