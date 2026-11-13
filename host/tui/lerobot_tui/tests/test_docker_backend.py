import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from lerobot_tui.backends.docker import (
    ComposeService,
    DockerComposeError,
    DockerComposeManager,
)


class FakeProcess:
    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ) -> None:
        self.stdout = stdout.encode()
        self.stderr = stderr.encode()
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout, self.stderr


class DockerComposeManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        repository_root = Path(__file__).resolve().parents[4]
        self.compose_file = repository_root / "docker" / "deploy" / "compose.yaml"
        self.manager = DockerComposeManager(self.compose_file)

    async def test_services_are_sorted_and_unique(self) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=FakeProcess("zeta\nalpha\nzeta\n")),
        ):
            services = await self.manager.get_services()

        self.assertEqual(services, ["alpha", "zeta"])

    async def test_empty_service_list_is_empty(self) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=FakeProcess()),
        ):
            self.assertEqual(await self.manager.get_services(), [])

    async def test_status_accepts_json_array_and_json_lines(self) -> None:
        status_records = [
            {"Service": "alpha", "State": "running", "Status": "Up 3 minutes"},
            {"Service": "zeta", "State": "exited", "Status": "Exited (0)"},
        ]
        outputs = [
            json.dumps(status_records),
            "\n".join(json.dumps(record) for record in status_records),
        ]

        for output in outputs:
            with (
                self.subTest(output=output),
                patch(
                    "asyncio.create_subprocess_exec",
                    new=AsyncMock(return_value=FakeProcess(output)),
                ),
            ):
                services = await self.manager.get_status()

            self.assertEqual(
                services,
                [
                    ComposeService("alpha", "Up 3 minutes", "running"),
                    ComposeService("zeta", "Exited (0)", "exited"),
                ],
            )

    async def test_empty_status_is_empty(self) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=FakeProcess()),
        ):
            self.assertEqual(await self.manager.get_status(), [])

    async def test_mixed_replica_status_is_running_when_any_replica_runs(self) -> None:
        output = json.dumps(
            [
                {"Service": "sample", "State": "running", "Status": "Up 3 minutes"},
                {"Service": "sample", "State": "exited", "Status": "Exited (0)"},
            ]
        )
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=FakeProcess(output)),
        ):
            services = await self.manager.get_status()

        self.assertEqual(
            services,
            [ComposeService("sample", "Exited (0); Up 3 minutes", "running")],
        )

    async def test_invalid_status_json_is_reported(self) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=FakeProcess("{invalid")),
        ):
            with self.assertRaisesRegex(DockerComposeError, "invalid service status JSON"):
                await self.manager.get_status()

    async def test_lifecycle_and_image_commands_do_not_build(self) -> None:
        subprocess = AsyncMock(return_value=FakeProcess("service logs"))
        with patch("asyncio.create_subprocess_exec", new=subprocess):
            await self.manager.start("sample")
            await self.manager.stop("sample")
            await self.manager.restart("sample")
            logs = await self.manager.logs("sample")
            await self.manager.pull("sample")
            await self.manager.recreate("sample")

        self.assertEqual(logs, "service logs")
        self.assertEqual(
            [call.args[4:] for call in subprocess.await_args_list],
            [
                ("up", "-d", "--no-build", "sample"),
                ("stop", "sample"),
                ("restart", "sample"),
                ("logs", "--tail", "100", "sample"),
                ("pull", "sample"),
                ("up", "-d", "--no-build", "--no-deps", "--force-recreate", "sample"),
            ],
        )

    async def test_command_failure_includes_compose_error(self) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=FakeProcess(stderr="permission denied", returncode=1)),
        ):
            with self.assertRaisesRegex(DockerComposeError, "permission denied"):
                await self.manager.stop("sample")

    async def test_development_compose_file_is_rejected(self) -> None:
        repository_root = Path(__file__).resolve().parents[4]
        development_compose = repository_root / "docker" / "dev" / "compose.yaml"

        with self.assertRaisesRegex(ValueError, "docker/deploy"):
            DockerComposeManager(development_compose)


if __name__ == "__main__":
    unittest.main()
