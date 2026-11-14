import json
import os
import signal
import subprocess
import sys
import tempfile
import termios
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from lerobot_tui.backends.docker import (
    _INTERACTIVE_EXEC,
    DEPLOY_COMPOSE_FILES,
    ComposeService,
    DockerComposeError,
    DockerComposeManager,
    ToolExecutionResult,
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
        self.pid = 12345

    async def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout, self.stderr

    async def wait(self) -> int:
        return self.returncode


class DockerComposeManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        repository_root = Path(__file__).resolve().parents[4]
        self.compose_file = repository_root / "docker" / "deploy" / "compose.yaml"
        self.manager = DockerComposeManager(self.compose_file)

    @staticmethod
    def temporary_manager(root: Path) -> DockerComposeManager:
        deploy = root / "docker" / "deploy"
        deploy.mkdir(parents=True)
        for filename, _ in DEPLOY_COMPOSE_FILES:
            (deploy / filename).write_text("services: {}\n", encoding="utf-8")
        return DockerComposeManager(deploy / "compose.yaml")

    @contextmanager
    def fake_terminal(self) -> Iterator[None]:
        def kill_group(_group: int, sig: int) -> None:
            if sig == 0:
                raise ProcessLookupError

        with (
            patch("os.tcgetpgrp", return_value=42),
            patch("os.getpgrp", return_value=42),
            patch("os.getpgid", return_value=12345),
            patch("os.tcsetpgrp"),
            patch("os.killpg", side_effect=kill_group),
            patch("termios.tcgetattr", return_value=[0, 0, 0, termios.ISIG, 0, 0, []]),
            patch("termios.tcsetattr"),
            patch("termios.tcflush"),
            patch("select.select", return_value=([0], [], [])),
            patch("os.read", return_value=b"\n"),
        ):
            yield

    async def test_services_are_sorted_and_unique(self) -> None:
        outputs = [
            json.dumps({"services": {"zeta": {}, "alpha": {}, "hiwonder-scan-leader": {}}}),
            json.dumps({"services": {"zeta": {}, "alpha": {}}}),
            json.dumps({"services": {}}),
            json.dumps({"services": {"alpha": {}}}),
            json.dumps({"services": {}}),
            json.dumps({"services": {"hiwonder-scan-leader": {}}}),
        ]
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=[FakeProcess(output) for output in outputs]),
        ):
            services = await self.manager.get_services()

        self.assertEqual(services, ["alpha", "hiwonder-scan-leader", "zeta"])

    async def test_empty_service_list_is_empty(self) -> None:
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(
                side_effect=[
                    FakeProcess(json.dumps({"services": {}})),
                    *(FakeProcess(json.dumps({"services": {}})) for _ in range(5)),
                ]
            ),
        ):
            self.assertEqual(await self.manager.get_services(), [])

    async def test_catalog_assigns_categories_and_execution_types(self) -> None:
        compose_config = {
            "services": {
                "alpha": {},
                "calibration": {
                    "image": "example/calibration:1",
                    "command": ["lerobot-calibrate", "/dev/hiwonder"],
                },
                "hiwonder-find-port": {},
                "hiwonder-scan-leader": {},
            }
        }
        outputs = [
            json.dumps(compose_config),
            json.dumps({"services": {"alpha": {}}}),
            json.dumps({"services": {}}),
            json.dumps({"services": {"alpha": {}}}),
            json.dumps(
                {
                    "services": {
                        "calibration": {
                            "command": [
                                "lerobot-calibrate",
                                "/dev/hiwonder",
                                "${LEADER_CALIBRATION_FILE:-/config/calibration/5dof/leader.yaml}",
                            ],
                            "environment": {"CALIBRATION_MODE": "configured"},
                        }
                    }
                }
            ),
            json.dumps({"services": {"hiwonder-find-port": {}, "hiwonder-scan-leader": {}}}),
        ]
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(side_effect=[FakeProcess(output) for output in outputs]),
        ):
            catalog = await self.manager.get_catalog()

        self.assertEqual(
            [(service.name, service.category, service.execution_type) for service in catalog],
            [
                ("alpha", "Motion", "service"),
                ("calibration", "Calibration", "service"),
                ("hiwonder-find-port", "Tools", "interactive"),
                ("hiwonder-scan-leader", "Tools", "one-shot"),
            ],
        )
        calibration = next(service for service in catalog if service.name == "calibration")
        self.assertEqual(calibration.source_compose, "docker/deploy/compose.calibration.yaml")
        self.assertEqual(calibration.image, "example/calibration:1")
        self.assertEqual(calibration.command, "lerobot-calibrate /dev/hiwonder")
        self.assertEqual(calibration.dockerfile, "Not specified")
        self.assertEqual(calibration.documentation, "docs/usage.md")
        self.assertEqual(
            calibration.environment_variables,
            ("CALIBRATION_MODE", "LEADER_CALIBRATION_FILE"),
        )

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

    def test_calibration_defaults_and_paths_preserve_robot_and_dof(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            manager = self.temporary_manager(Path(temporary_directory))
            self.assertEqual(
                manager.default_calibration_file("LEADER_CALIBRATION_FILE", "5"),
                "/config/calibration/5dof/leader_example_calibration.yaml",
            )
            self.assertEqual(
                manager.default_calibration_file("FOLLOWER_CALIBRATION_FILE", "6"),
                "/config/calibration/6dof/follower_example_calibration.yaml",
            )

            custom_leader = manager.calibration_root / "custom" / "leader.yaml"
            custom_follower = manager.calibration_root / "custom" / "follower.yml"
            leader_container, leader_host = manager.prepare_calibration_output(str(custom_leader))
            follower_container, follower_host = manager.prepare_calibration_output(
                str(custom_follower)
            )
            self.assertEqual(leader_container, "/config/calibration/custom/leader.yaml")
            self.assertEqual(follower_container, "/config/calibration/custom/follower.yml")
            self.assertNotEqual(leader_host, follower_host)
            self.assertTrue(leader_host.parent.is_dir())
            self.assertTrue(follower_host.parent.is_dir())

    def test_calibration_paths_reject_escape_and_invalid_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            manager = self.temporary_manager(Path(temporary_directory))
            for value in (
                "relative/calibration.yaml",
                "/tmp/calibration.yaml",
                "/config/calibration/../outside.yaml",
                "/config/calibration/not-calibration.txt",
            ):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    manager.resolve_calibration_path(value)

    def test_calibration_persistence_keeps_leader_and_follower_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            deploy = root / "docker" / "deploy"
            deploy.mkdir(parents=True)
            for filename, _ in DEPLOY_COMPOSE_FILES:
                (deploy / filename).write_text("services: {}\n", encoding="utf-8")
            dotenv = deploy / ".env"
            dotenv.write_text("KEEP_ME=unchanged\n", encoding="utf-8")
            manager = DockerComposeManager(deploy / "compose.yaml")
            leader = str(manager.calibration_root / "team" / "leader.yaml")
            follower = str(manager.calibration_root / "team" / "follower.yaml")

            leader_value, _ = manager.save_calibration_file("LEADER_CALIBRATION_FILE", leader)
            follower_value, _ = manager.save_calibration_file("FOLLOWER_CALIBRATION_FILE", follower)

            self.assertEqual(manager.environment_value("LEADER_CALIBRATION_FILE"), leader_value)
            self.assertEqual(manager.environment_value("FOLLOWER_CALIBRATION_FILE"), follower_value)
            self.assertIn("KEEP_ME=unchanged\n", dotenv.read_text(encoding="utf-8"))
            self.assertIn(f"LEADER_CALIBRATION_FILE='{leader_value}'", dotenv.read_text())
            self.assertIn(f"FOLLOWER_CALIBRATION_FILE='{follower_value}'", dotenv.read_text())

    def test_bringup_validates_only_its_required_calibration_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            deploy = root / "docker" / "deploy"
            deploy.mkdir(parents=True)
            for filename, _ in DEPLOY_COMPOSE_FILES:
                (deploy / filename).write_text("services: {}\n", encoding="utf-8")
            calibration_root = deploy / "config" / "calibration"
            leader = calibration_root / "custom" / "leader.yaml"
            follower = calibration_root / "custom" / "follower.yaml"
            leader.parent.mkdir(parents=True)
            leader.write_text("leader: true\n", encoding="utf-8")
            follower.write_text("follower: true\n", encoding="utf-8")
            (deploy / ".env").write_text(
                "LEADER_CALIBRATION_FILE=/config/calibration/custom/leader.yaml\n"
                "FOLLOWER_CALIBRATION_FILE=/config/calibration/custom/follower.yaml\n"
                "LEADER_DOF=6\nFOLLOWER_DOF=5\n",
                encoding="utf-8",
            )
            manager = DockerComposeManager(deploy / "compose.yaml")

            manager._validate_bringup_calibrations("so101-leader-bringup")
            manager._validate_bringup_calibrations("so101-follower-bringup")
            manager._validate_bringup_calibrations("so101-leader-follower-bringup")

            follower.unlink()
            manager._validate_bringup_calibrations("so101-leader-bringup")
            with self.assertRaisesRegex(ValueError, "does not exist or is unreadable"):
                manager._validate_bringup_calibrations("so101-leader-follower-bringup")

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
        compose_prefix = [
            "docker",
            "compose",
            *(
                argument
                for compose_file in self.manager._compose_files
                for argument in ("-f", str(compose_file))
            ),
        ]
        expected = [
            compose_prefix + ["up", "-d", "--no-build", "sample"],
            compose_prefix + ["stop", "sample"],
            compose_prefix + ["restart", "sample"],
            compose_prefix + ["logs", "--tail", "100", "sample"],
            compose_prefix + ["pull", "sample"],
            compose_prefix + ["up", "-d", "--no-build", "--no-deps", "--force-recreate", "sample"],
        ]
        self.assertEqual(
            [list(call.args) for call in subprocess.await_args_list],
            expected,
        )

    async def test_one_shot_run_uses_supported_args_and_full_compose_configuration(self) -> None:
        subprocess = AsyncMock(
            return_value=FakeProcess(stdout="found motors", stderr="warning", returncode=2)
        )
        with patch("asyncio.create_subprocess_exec", new=subprocess):
            result = await self.manager.run_tool(
                "lerobot-list-cameras",
                {},
            )

        self.assertEqual(result, ToolExecutionResult(2, "found motors", "warning"))
        compose_prefix = [
            "docker",
            "compose",
            *(
                argument
                for compose_file in self.manager._compose_files
                for argument in ("-f", str(compose_file))
            ),
        ]
        self.assertEqual(
            list(subprocess.await_args.args),
            compose_prefix + ["run", "--rm", "--no-deps", "lerobot-list-cameras"],
        )
        self.assertNotIn("--no-build", subprocess.await_args.args)
        self.assertEqual(
            subprocess.await_args.kwargs["cwd"],
            self.compose_file.parent,
        )
        self.assertIn("PATH", subprocess.await_args.kwargs["env"])

    async def test_one_shot_tool_captures_output_and_environment(self) -> None:
        subprocess = AsyncMock(return_value=FakeProcess(stdout="found motors", returncode=2))
        with patch("asyncio.create_subprocess_exec", new=subprocess):
            result = await self.manager.run_tool(
                "hiwonder-scan-leader",
                {"LEADER_PORT": "/dev/ttyUSB0"},
            )

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.stdout, "found motors")
        self.assertEqual(
            subprocess.await_args.kwargs["env"]["LEADER_PORT"],
            "/dev/ttyUSB0",
        )

    async def test_interactive_ctrl_c_interrupts_and_reaps_child(self) -> None:
        class RunningProcess:
            pid = 12345
            returncode: int | None = None

            def poll(self) -> int | None:
                return self.returncode

            def wait(self, timeout: float | None = None) -> int:
                if self.returncode is None:
                    os.kill(os.getpid(), signal.SIGINT)
                    raise subprocess.TimeoutExpired("docker", timeout)
                assert self.returncode is not None
                return self.returncode

        process = RunningProcess()

        def send_signal(group: int, sig: int) -> None:
            self.assertEqual(group, process.pid)
            if sig == 0 and process.returncode is not None:
                raise ProcessLookupError
            if sig == signal.SIGINT:
                process.returncode = 130

        previous_handler = signal.getsignal(signal.SIGINT)
        remove = Mock()
        with (
            self.fake_terminal(),
            patch("os.killpg", side_effect=send_signal),
            patch("subprocess.Popen", return_value=process),
            patch.object(self.manager, "_remove_interactive_container", new=remove),
            patch("os.tcsetpgrp") as foreground,
            patch("termios.tcsetattr") as restore,
        ):
            self.assertIsNone(self.manager.run_interactive_tool("hiwonder-find-port", {}))

            self.assertEqual(foreground.call_args_list[-1].args[1], 42)
            restore.assert_called_once()
            remove.assert_called_once()
            self.assertEqual(signal.getsignal(signal.SIGINT), previous_handler)

    async def test_interactive_exit_130_displays_failure_before_confirmation(self) -> None:
        remove = Mock()
        process = Mock(pid=12345)
        process.poll.return_value = 130
        process.wait.return_value = 130
        shown = Mock(side_effect=lambda _service, _code: self.assertEqual(process.poll(), 130))
        confirmation = Mock(return_value=True)
        with (
            self.fake_terminal(),
            patch("subprocess.Popen", return_value=process),
            patch.object(self.manager, "_remove_interactive_container", new=remove),
            patch.object(self.manager, "_show_interactive_result", new=shown),
            patch.object(self.manager, "_wait_for_interactive_confirmation", new=confirmation),
        ):
            self.assertEqual(self.manager.run_interactive_tool("hiwonder-find-port", {}), 130)
        shown.assert_called_once_with("hiwonder-find-port", 130)
        confirmation.assert_called_once()
        remove.assert_not_called()

    async def test_interactive_confirmation_waits_after_exit_and_flushes_input(
        self,
    ) -> None:
        process = Mock(pid=12345)
        process.poll.return_value = 4
        process.wait.return_value = 4
        order: list[str] = []

        def display(_service: str, exit_code: int) -> None:
            self.assertEqual(exit_code, 4)
            self.assertEqual(process.poll(), 4)
            order.append("display")

        def confirm(_terminal: int, _interrupted: object) -> bool:
            order.append("confirm")
            return True

        with (
            self.fake_terminal(),
            patch("subprocess.Popen", return_value=process),
            patch.object(self.manager, "_show_interactive_result", side_effect=display),
            patch.object(self.manager, "_wait_for_interactive_confirmation", side_effect=confirm),
        ):
            result = self.manager.run_interactive_tool("hiwonder-find-port", {})
        self.assertEqual(result, 4)
        self.assertEqual(order, ["display", "confirm"])

    async def test_interactive_cancellation_reaps_process_and_restores_terminal(self) -> None:
        process = Mock(pid=12345)
        process.poll.return_value = None

        def wait(timeout: float | None = None) -> int:
            if process.poll.return_value is not None:
                return process.poll.return_value
            os.kill(os.getpid(), signal.SIGINT)
            raise subprocess.TimeoutExpired("docker", timeout)

        process.wait.side_effect = wait

        def stop_process(_process: Mock) -> None:
            process.poll.return_value = 130

        stop = Mock(side_effect=stop_process)
        remove = Mock()
        with (
            self.fake_terminal(),
            patch("subprocess.Popen", return_value=process),
            patch.object(self.manager, "_stop_interactive_process", new=stop),
            patch.object(self.manager, "_remove_interactive_container", new=remove),
            patch("os.tcsetpgrp") as foreground,
            patch("termios.tcsetattr") as restore,
        ):
            self.assertIsNone(self.manager.run_interactive_tool("hiwonder-find-port", {}))
            stop.assert_called_once_with(process)
            remove.assert_called_once()
            self.assertEqual(foreground.call_args_list[-1].args[1], 42)
            restore.assert_called_once()

    async def test_interactive_shutdown_escalates_and_reaps_process(self) -> None:
        process = Mock(pid=12345)
        process.poll.return_value = None
        process.wait.side_effect = [
            subprocess.TimeoutExpired("docker", 5),
            subprocess.TimeoutExpired("docker", 2),
            -signal.SIGKILL,
        ]
        with patch("os.killpg") as kill_group:
            self.manager._stop_interactive_process(process)
        self.assertEqual(
            [call.args for call in kill_group.call_args_list],
            [(12345, signal.SIGINT), (12345, signal.SIGTERM), (12345, signal.SIGKILL)],
        )
        self.assertEqual(process.wait.call_count, 3)

    async def test_raw_terminal_keeps_ctrl_c_without_enabling_other_signal_keys(self) -> None:
        attributes = [0, 0, 0, 0, 0, 0, [b"\x1c"] * 32]
        with (
            patch("termios.tcgetattr", return_value=attributes),
            patch("termios.tcsetattr") as set_attributes,
            patch("os.fpathconf", return_value=0),
        ):
            self.manager._keep_terminal_interruptible(0)
        self.assertTrue(attributes[3] & termios.ISIG)
        self.assertEqual(attributes[6][termios.VQUIT], b"\x00")
        self.assertEqual(attributes[6][termios.VSUSP], b"\x00")
        set_attributes.assert_called_once()

    async def test_remaining_interactive_group_is_killed_after_grace_period(self) -> None:
        with (
            patch("os.killpg") as kill_group,
            patch("time.monotonic", side_effect=[0, 2]),
        ):
            self.manager._finish_interactive_group(12345)
        self.assertEqual(
            [call.args for call in kill_group.call_args_list],
            [(12345, 0), (12345, signal.SIGKILL)],
        )

    async def test_interactive_spawn_error_restores_terminal_and_signal_handler(self) -> None:
        previous_handler = signal.getsignal(signal.SIGINT)
        with (
            self.fake_terminal(),
            patch("subprocess.Popen", side_effect=OSError("cannot start")),
            patch("os.tcsetpgrp") as foreground,
            patch("termios.tcsetattr") as restore,
        ):
            with self.assertRaisesRegex(DockerComposeError, "cannot start"):
                self.manager.run_interactive_tool("hiwonder-find-port", {})
            self.assertEqual(foreground.call_args_list[-1].args[1], 42)
            restore.assert_called_once()
            self.assertEqual(signal.getsignal(signal.SIGINT), previous_handler)

    async def test_interactive_container_cleanup_reports_daemon_failure(self) -> None:
        failure = subprocess.CompletedProcess(["docker"], 1, b"", b"daemon unavailable")
        with patch("subprocess.run", return_value=failure) as run:
            with self.assertRaisesRegex(DockerComposeError, "daemon unavailable"):
                self.manager._remove_interactive_container("lerobot-tui-test")
        self.assertEqual(run.call_args.args[0], ["docker", "rm", "-f", "lerobot-tui-test"])

    async def test_interactive_tool_uses_tty_and_full_compose_configuration(self) -> None:
        compose_prefix = [
            "docker",
            "compose",
            *(
                argument
                for compose_file in self.manager._compose_files
                for argument in ("-f", str(compose_file))
            ),
        ]
        services = (
            "hiwonder-find-port",
            "lerobot-calibrate-leader",
            "lerobot-calibrate-follower",
            "hiwonder-setup-motors-leader",
            "hiwonder-setup-motors-follower",
        )
        for service in services:
            with self.subTest(service=service):
                process = Mock(pid=12345)
                process.poll.return_value = 7
                process.wait.return_value = 7
                result_summary = Mock()
                confirmation = Mock(return_value=True)
                with (
                    self.fake_terminal(),
                    patch("subprocess.Popen", return_value=process) as popen,
                    patch.object(self.manager, "_show_interactive_result", new=result_summary),
                    patch.object(
                        self.manager,
                        "_wait_for_interactive_confirmation",
                        new=confirmation,
                    ),
                ):
                    exit_code = self.manager.run_interactive_tool(
                        service,
                        (
                            {"LEADER_PORT": "/dev/ttyUSB0"}
                            if service != "hiwonder-find-port"
                            else {}
                        ),
                    )
                self.assertEqual(exit_code, 7)
                result_summary.assert_called_once_with(service, 7)
                confirmation.assert_called_once()
                args = popen.call_args.args[0]
                self.assertEqual(
                    args[:3],
                    [
                        sys.executable,
                        "-c",
                        _INTERACTIVE_EXEC,
                    ],
                )
                command = args[3:]
                self.assertEqual(
                    command[:-2],
                    compose_prefix
                    + [
                        "run",
                        "--rm",
                        "--no-deps",
                        "--interactive",
                        "--name",
                    ],
                )
                self.assertTrue(command[-2].startswith("lerobot-tui-"))
                self.assertEqual(command[-1], service)
                self.assertNotIn("--no-build", args)
                self.assertNotIn("--no-tty", args)
                self.assertIsNone(popen.call_args.kwargs["stdin"])
                self.assertIsNone(popen.call_args.kwargs["stdout"])
                self.assertIsNone(popen.call_args.kwargs["stderr"])
                if service == "hiwonder-find-port":
                    self.assertNotIn("LEADER_PORT", popen.call_args.kwargs["env"])
                else:
                    self.assertEqual(
                        popen.call_args.kwargs["env"]["LEADER_PORT"],
                        "/dev/ttyUSB0",
                    )

    async def test_stopped_state_requires_explicit_stop_action(self) -> None:
        exited_status = json.dumps(
            [{"Service": "sample", "State": "exited", "Status": "Exited (0)"}]
        )
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=FakeProcess(exited_status)),
        ):
            before_stop = await self.manager.get_status()
        self.assertEqual(before_stop[0].state, "exited")

        with (
            patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=FakeProcess())),
        ):
            await self.manager.stop("sample")
        with patch(
            "asyncio.create_subprocess_exec",
            new=AsyncMock(return_value=FakeProcess(exited_status)),
        ):
            after_stop = await self.manager.get_status()
        self.assertEqual(after_stop[0].state, "stopped")

    async def test_tool_compose_interpolation_retains_parent_environment(self) -> None:
        process = Mock(pid=12345)
        process.poll.return_value = 0
        process.wait.return_value = 0
        with (
            self.fake_terminal(),
            patch.dict(os.environ, {"LEROBOT_TEST_VALUE": "from-parent"}),
            patch("subprocess.Popen", return_value=process) as popen,
            patch.object(self.manager, "_wait_for_interactive_confirmation", return_value=True),
        ):
            self.manager.run_interactive_tool(
                "hiwonder-find-port",
                {"CUSTOM_VALUE": "configured"},
            )

        environment = popen.call_args.kwargs["env"]
        self.assertEqual(environment["LEROBOT_TEST_VALUE"], "from-parent")
        self.assertEqual(environment["CUSTOM_VALUE"], "configured")

    async def test_nonzero_tool_exit_is_reported_without_hiding_output(self) -> None:
        subprocess = AsyncMock(
            return_value=FakeProcess(stdout="partial result", stderr="device busy", returncode=125)
        )
        with patch("asyncio.create_subprocess_exec", new=subprocess):
            result = await self.manager.run_tool("lerobot-list-cameras", {})

        self.assertEqual(result.exit_code, 125)
        self.assertEqual(result.stdout, "partial result")
        self.assertEqual(result.stderr, "device busy")

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
