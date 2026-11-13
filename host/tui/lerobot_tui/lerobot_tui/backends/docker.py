import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DockerComposeError(RuntimeError):
    """Raised when a Docker Compose command cannot be completed."""


@dataclass(frozen=True, slots=True)
class ComposeService:
    name: str
    status: str
    state: str


class DockerComposeManager:
    def __init__(
        self,
        compose_file: Path,
        project_name: str | None = None,
    ) -> None:
        self._compose_file = compose_file.resolve()
        self._project_name = project_name

        if (
            self._compose_file.parent.name != "deploy"
            or self._compose_file.parent.parent.name != "docker"
        ):
            raise ValueError("The TUI only manages Compose files in docker/deploy.")
        if not self._compose_file.is_file():
            raise FileNotFoundError(f"Compose file not found: {self._compose_file}")

    async def _execute(self, *args: str) -> str:
        command = ["docker", "compose", "-f", str(self._compose_file)]
        if self._project_name is not None:
            command.extend(["-p", self._project_name])
        command.extend(args)

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=self._compose_file.parent,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise DockerComposeError(
                "Docker CLI not found. Install Docker with the Compose plugin."
            ) from exc
        except PermissionError as exc:
            raise DockerComposeError(f"Cannot execute Docker CLI: {exc}") from exc
        except OSError as exc:
            raise DockerComposeError(f"Could not start Docker CLI: {exc}") from exc

        try:
            stdout, stderr = await process.communicate()
        except asyncio.CancelledError:
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(process.communicate(), timeout=1)
            except TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.communicate()
            raise

        if process.returncode != 0:
            details = stderr.decode(errors="replace").strip()
            if not details:
                details = stdout.decode(errors="replace").strip()
            if not details:
                details = f"Docker Compose exited with status {process.returncode}."
            raise DockerComposeError(details)

        return stdout.decode(errors="replace").strip()

    async def get_services(self) -> list[str]:
        output = await self._execute("--profile", "*", "config", "--services")
        return sorted({line.strip() for line in output.splitlines() if line.strip()})

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
            services.append(
                ComposeService(
                    name=name,
                    state=state,
                    status="; ".join(statuses),
                )
            )
        return services

    async def start(self, service: str) -> None:
        await self._execute("up", "-d", "--no-build", service)

    async def stop(self, service: str) -> None:
        await self._execute("stop", service)

    async def restart(self, service: str) -> None:
        await self._execute("restart", service)

    async def logs(self, service: str) -> str:
        return await self._execute("logs", "--tail", "100", service)

    async def pull(self, service: str) -> None:
        await self._execute("pull", service)

    async def recreate(self, service: str) -> None:
        await self._execute(
            "up",
            "-d",
            "--no-build",
            "--no-deps",
            "--force-recreate",
            service,
        )
