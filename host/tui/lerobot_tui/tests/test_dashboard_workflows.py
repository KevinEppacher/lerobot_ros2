import asyncio
import os
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from lerobot_tui.app import LeRobotApp
from lerobot_tui.backends.docker import (
    TOOL_METADATA,
    ComposeService,
    DockerComposeError,
    ToolExecutionResult,
    ToolMetadata,
)
from lerobot_tui.screens.operation_error import OperationErrorScreen
from lerobot_tui.screens.service_info import ServiceInfoScreen
from lerobot_tui.screens.service_logs import ServiceLogsScreen
from lerobot_tui.screens.tool_dialogs import (
    ToolConfigurationScreen,
    ToolExecutionConfirmation,
    ToolOutputScreen,
)
from lerobot_tui.screens.update_confirmation import UpdateConfirmation
from lerobot_tui.widgets.dashboard_view import DashboardView
from lerobot_tui.widgets.service_table import ServiceTable
from lerobot_tui.widgets.services_view import ServicesView
from rich.color_triplet import ColorTriplet
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Header, Input, Static, TabbedContent, TabPane


class FakeDockerManager:
    def __init__(self, state: str = "running") -> None:
        self.state = state
        self.calls: list[str] = []
        self.error: str | None = None
        self.status_error: str | None = None
        self.wait_for_start = False
        self.start_started = asyncio.Event()
        self.release_start = asyncio.Event()
        self.catalog = [ComposeService("sample", state, state)]
        self.environment: dict[str, str] = {}
        self.tool_calls: list[tuple[str, dict[str, str]]] = []
        self.tool_result = ToolExecutionResult(0, "tool output", "")
        self.interactive_error: str | None = None
        self.interactive_interrupt = False
        self.interactive_cancel = False
        self.interactive_exit_code = 0
        self.interactive_calls: list[tuple[str, dict[str, str]]] = []

    async def get_services(self) -> list[str]:
        return ["sample"]

    async def get_catalog(self) -> list[ComposeService]:
        return self.catalog

    async def get_status(self) -> list[ComposeService]:
        if self.status_error:
            raise DockerComposeError(self.status_error)
        if self.state == "not created":
            return []
        return [ComposeService("sample", self.state, self.state)]

    def metadata_for(self, service: str) -> ToolMetadata:
        return TOOL_METADATA.get(service, ToolMetadata("service"))

    def environment_value(self, key: str) -> str:
        return self.environment.get(key, "")

    def default_calibration_file(self, variable: str, dof: str) -> str:
        robot = variable.removesuffix("_CALIBRATION_FILE").lower()
        return f"/config/calibration/{dof}dof/{robot}_example_calibration.yaml"

    def calibration_files(self) -> list[tuple[str, str]]:
        return []

    def calibration_directories(self) -> list[tuple[str, str]]:
        return []

    def resolve_calibration_path(self, value: str) -> Path:
        return Path(value)

    def save_calibration_file(self, variable: str, value: str) -> tuple[str, Path]:
        return value, Path(value)

    def prepare_calibration_output(self, value: str) -> tuple[str, Path]:
        return value, Path(value)

    async def active_services_using_device(self, device: str) -> list[str]:
        return []

    async def run_tool(
        self,
        service: str,
        environment: dict[str, str],
    ) -> ToolExecutionResult:
        self.tool_calls.append((service, environment))
        return self.tool_result

    def run_interactive_tool(
        self,
        service: str,
        environment: dict[str, str],
    ) -> int | None:
        self.interactive_calls.append((service, environment))
        if self.interactive_cancel:
            raise asyncio.CancelledError
        if self.interactive_interrupt:
            raise KeyboardInterrupt
        if self.interactive_error:
            raise DockerComposeError(self.interactive_error)
        return self.interactive_exit_code

    async def start(self, service: str) -> None:
        self.calls.append(f"start:{service}")
        self.start_started.set()
        if self.wait_for_start:
            await self.release_start.wait()
        if self.error:
            raise DockerComposeError(self.error)

    async def stop(self, service: str) -> None:
        self.calls.append(f"stop:{service}")

    async def restart(self, service: str) -> None:
        self.calls.append(f"restart:{service}")

    async def pull(self, service: str) -> None:
        self.calls.append(f"pull:{service}")

    async def recreate(self, service: str) -> None:
        self.calls.append(f"recreate:{service}")

    async def logs(self, service: str) -> str:
        self.calls.append(f"logs:{service}")
        return "sample log output"


class ServicesTestApp(App[None]):
    CSS_PATH = Path(__file__).parents[1] / "lerobot_tui" / "styles" / "app.tcss"

    def __init__(self, manager: FakeDockerManager) -> None:
        super().__init__()
        self.manager = manager

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="services", id="main-tabs"):
            yield TabPane("Dashboard", DashboardView(), id="dashboard")
            yield TabPane("Services", ServicesView(self.manager), id="services")

    def on_services_view_updated(self, event: ServicesView.Updated) -> None:
        self.query_one(DashboardView).update_docker_status(event.services, event.connected)


class DashboardWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def assert_button_contrast(self, app: App[None], button: Button) -> None:
        region = button.content_region
        style = app.screen.get_style_at(region.x + region.width // 2, region.y)
        self.assertIsNotNone(style.color)
        self.assertIsNotNone(style.bgcolor)
        assert style.color is not None and style.bgcolor is not None

        def luminance(rgb: ColorTriplet) -> float:
            channels = [component / 255 for component in rgb]
            linear = [
                channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
                for channel in channels
            ]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        light, dark = sorted(
            (luminance(style.color.get_truecolor()), luminance(style.bgcolor.get_truecolor())),
            reverse=True,
        )
        self.assertGreaterEqual((light + 0.05) / (dark + 0.05), 4.5, f"{button.id}: {style}")

    async def test_host_application_has_all_tabs_and_number_navigation(self) -> None:
        manager = FakeDockerManager()
        compose_file = Path(__file__).resolve().parents[4] / "docker" / "deploy" / "compose.yaml"
        with (
            patch.dict(os.environ, {"LEROBOT_COMPOSE_FILE": str(compose_file)}),
            patch("lerobot_tui.app.DockerComposeManager", return_value=manager),
        ):
            app = LeRobotApp()
            async with app.run_test(size=(100, 32)) as pilot:
                await pilot.pause()
                tabs = app.query_one(TabbedContent)
                self.assertEqual(len(tabs.query(TabPane)), 5)

                await pilot.press("2")
                self.assertEqual(tabs.active, "services")
                await pilot.pause()
                self.assertEqual(
                    app.query_one(ServiceTable).get_selected_service(),
                    "sample",
                )
                await pilot.press("1")
                await pilot.click("#open-services")
                self.assertEqual(tabs.active, "services")
                await pilot.press("4")
                self.assertEqual(tabs.active, "wifi")
                await pilot.press("1")
                self.assertEqual(tabs.active, "dashboard")

    async def test_ascii_logos_are_mounted_visible_and_not_global(self) -> None:
        manager = FakeDockerManager()
        compose_file = Path(__file__).resolve().parents[4] / "docker" / "deploy" / "compose.yaml"
        with (
            patch.dict(os.environ, {"LEROBOT_COMPOSE_FILE": str(compose_file)}),
            patch("lerobot_tui.app.DockerComposeManager", return_value=manager),
        ):
            app = LeRobotApp()
            async with app.run_test(size=(100, 32)) as pilot:
                logos = (
                    ("dashboard-logo", "1"),
                    ("services-logo", "2"),
                    ("robots-logo", "3"),
                    ("wifi-logo", "4"),
                    ("settings-logo", "5"),
                )
                self.assertEqual(app.query_one(Header).icon, "")
                for logo_id, key in logos:
                    logo = app.query_one(f"#{logo_id}", Static)
                    self.assertTrue(logo.is_mounted)
                    self.assertTrue(logo.render().plain.strip())
                    await pilot.press(key)
                    await pilot.pause()
                    self.assertTrue(logo.visible)

                self.assertIn("WIFI", app.query_one("#wifi-logo", Static).render().plain)
                self.assertIn("SETTINGS", app.query_one("#settings-logo", Static).render().plain)
                self.assertNotEqual(
                    app.query_one("#wifi-logo", Static).render().plain,
                    app.query_one("#settings-logo", Static).render().plain,
                )
                root = ET.fromstring(app.export_screenshot())
                visible_text = [
                    "".join(node.itertext()) for node in root.iter() if node.tag.endswith("text")
                ]
                self.assertNotIn("⭘", visible_text)
                self.assertNotIn("0", visible_text)

    async def test_dashboard_summarizes_service_states(self) -> None:
        manager = FakeDockerManager("running")
        app = ServicesTestApp(manager)

        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            dashboard = app.query_one(DashboardView)
            self.assertEqual(
                str(dashboard.query_one("#service-summary").render()),
                "Running: 1    Stopped: 0    Failed: 0",
            )
            self.assertIn(
                "unavailable until the robot interface",
                str(dashboard.query_one("#robot-summary").render()),
            )

    async def test_service_table_actions_and_logs_are_visible_and_usable(self) -> None:
        manager = FakeDockerManager()
        app = ServicesTestApp(manager)

        async with app.run_test() as pilot:
            await pilot.pause()
            services = app.query_one(ServicesView)
            table = services.query_one(ServiceTable)
            table.focus()
            await pilot.pause()

            for button_id in (
                "start-service",
                "stop-service",
                "restart-service",
                "update-service",
                "service-logs",
            ):
                self.assertIsNotNone(services.query_one(f"#{button_id}"))

            await pilot.press("s")
            await pilot.pause()
            self.assertIn("start:sample", manager.calls)
            self.assertIn("Started: sample", str(services.query_one("#operation-status").render()))

            await pilot.click("#service-logs")
            await pilot.pause()
            self.assertIsInstance(app.screen, ServiceLogsScreen)
            self.assertEqual(app.screen._logs, "sample log output")

    async def test_failed_action_exposes_details_in_modal(self) -> None:
        manager = FakeDockerManager()
        manager.error = "container could not start"
        app = ServicesTestApp(manager)

        async with app.run_test() as pilot:
            await pilot.pause()
            services = app.query_one(ServicesView)
            services.query_one(ServiceTable).focus()
            await pilot.pause()
            services.action_start_service()
            await pilot.pause()
            await pilot.pause()

            self.assertFalse(services.query_one("#view-error").disabled)
            await pilot.click("#view-error")
            await pilot.pause()
            self.assertIsInstance(app.screen, OperationErrorScreen)
            self.assertIn(
                "container could not start",
                str(app.screen.query_one("#operation-error-details").render()),
            )

    async def test_running_service_recreation_requires_confirmation(self) -> None:
        manager = FakeDockerManager("running")
        app = ServicesTestApp(manager)

        async with app.run_test() as pilot:
            await pilot.pause()
            services = app.query_one(ServicesView)
            services.query_one(ServiceTable).focus()
            await pilot.pause()
            await pilot.press("u")
            await pilot.pause()
            await pilot.pause()
            self.assertIsInstance(app.screen, UpdateConfirmation)
            await pilot.click("#confirm-update")
            await pilot.pause()
            await pilot.pause()

        self.assertEqual(manager.calls, ["pull:sample", "recreate:sample"])

    async def test_stopped_service_image_pull_does_not_start_or_recreate(self) -> None:
        manager = FakeDockerManager("exited")
        app = ServicesTestApp(manager)

        async with app.run_test() as pilot:
            await pilot.pause()
            services = app.query_one(ServicesView)
            services.query_one(ServiceTable).focus()
            await pilot.pause()
            await pilot.press("u")
            await pilot.pause()
            await pilot.pause()
            self.assertEqual(manager.calls, ["pull:sample"])
            self.assertIn("remains stopped", str(services.query_one("#operation-status").render()))

    async def test_running_operation_has_visible_progress_feedback(self) -> None:
        manager = FakeDockerManager()
        manager.wait_for_start = True
        app = ServicesTestApp(manager)

        async with app.run_test() as pilot:
            await pilot.pause()
            services = app.query_one(ServicesView)
            services.query_one(ServiceTable).focus()
            await pilot.pause()
            await pilot.press("s")
            await asyncio.wait_for(manager.start_started.wait(), timeout=1)

            self.assertIn("Starting sample", str(services.query_one("#operation-status").render()))
            self.assertTrue(services.query_one("#operation-progress").display)
            self.assertTrue(services.query_one("#start-service").disabled)

            manager.release_start.set()
            await pilot.pause()
            await pilot.pause()
            self.assertIn("Started: sample", str(services.query_one("#operation-status").render()))
            self.assertFalse(services.query_one("#start-service").disabled)

    async def test_category_filter_and_tool_run_output(self) -> None:
        manager = FakeDockerManager()
        manager.catalog = [
            ComposeService("sample", "running", "running", "Bringup", "service"),
            ComposeService(
                "hiwonder-scan-leader",
                "Not created",
                "not created",
                "Tools",
                "one-shot",
            ),
        ]
        app = ServicesTestApp(manager)

        async with app.run_test() as pilot:
            await pilot.pause()
            services = app.query_one(ServicesView)
            table = services.query_one(ServiceTable)
            await pilot.click("#category-tools")
            await pilot.pause()

            self.assertEqual(table.row_count, 1)
            self.assertEqual(table.get_selected_service(), "hiwonder-scan-leader")
            self.assertEqual(table.get_cell("hiwonder-scan-leader", "category"), "Tools")
            services.action_start_service()
            self.assertEqual(manager.calls, [])
            self.assertIn(
                "only available for persistent services",
                str(services.query_one("#operation-status").render()),
            )

            await pilot.click("#configure-tool")
            await pilot.pause()
            self.assertEqual(app.screen.__class__.__name__, "ToolConfigurationScreen")
            app.screen.query_one("#config-LEADER_PORT", Input).value = "/dev/null"
            await pilot.click("#save-tool-config")
            await pilot.pause()

            await pilot.click("#run-tool")
            await pilot.pause()
            self.assertIsInstance(app.screen, ToolExecutionConfirmation)
            await pilot.click("#confirm-tool")
            await pilot.pause()
            await pilot.pause()

            self.assertEqual(
                manager.tool_calls,
                [("hiwonder-scan-leader", {"LEADER_PORT": "/dev/null"})],
            )
            self.assertIsInstance(app.screen, ToolOutputScreen)
            self.assertIn("tool output", app.screen.stdout)

    async def test_action_buttons_render_for_each_type_at_common_widths(self) -> None:
        for width in (80, 100, 120):
            with self.subTest(width=width):
                manager = FakeDockerManager("not created")
                manager.catalog = [
                    ComposeService("sample", "Not created", "not created", "Motion", "service"),
                    ComposeService(
                        "hiwonder-scan-leader", "Not created", "not created", "Tools", "one-shot"
                    ),
                    ComposeService(
                        "hiwonder-find-port",
                        "Not created",
                        "not created",
                        "Calibration",
                        "interactive",
                    ),
                ]
                app = ServicesTestApp(manager)
                async with app.run_test(size=(width, 32)) as pilot:
                    await pilot.pause()
                    services = app.query_one(ServicesView)
                    for category, expected in (
                        (
                            "Motion",
                            ("Start", "Stop", "Restart", "Update Image", "View Logs", "Info"),
                        ),
                        ("Tools", ("Configure", "Run", "View Output", "Info")),
                        ("Calibration", ("Configure", "Run Interactive", "Info")),
                    ):
                        services._set_category(category)
                        await pilot.pause()
                        buttons = [
                            button
                            for button in services.query("#service-actions Button")
                            if button.display
                        ]
                        self.assertEqual([str(button.label) for button in buttons], list(expected))
                        root = ET.fromstring(app.export_screenshot())
                        rendered = "".join(
                            "".join(node.itertext())
                            for node in root.iter()
                            if node.tag.endswith("text")
                        ).replace("\xa0", " ")
                        for label, button in zip(expected, buttons, strict=True):
                            self.assertIn(label, rendered)
                            self.assertEqual(button.region.height, 3)
                            self.assertGreaterEqual(button.content_region.width, len(label))
                            self.assertLessEqual(button.region.right, width)
                            self.assert_button_contrast(app, button)
                            if not button.disabled:
                                button.focus()
                                await pilot.pause()
                                self.assert_button_contrast(app, button)
                                await pilot.hover(button)
                                await pilot.pause()
                                self.assert_button_contrast(app, button)
                        if category == "Tools":
                            self.assertTrue(
                                services.query_one("#view-tool-output", Button).disabled
                            )
                            self.assertFalse(services.query_one("#run-tool", Button).disabled)
                        if category == "Calibration":
                            self.assertTrue(services.query_one("#configure-tool", Button).disabled)
                        enabled = next(button for button in buttons if not button.disabled)
                        enabled.focus()
                        await pilot.hover(enabled)
                        await pilot.pause()
                        root = ET.fromstring(app.export_screenshot())
                        self.assertIn(
                            str(enabled.label), "".join(root.itertext()).replace("\xa0", " ")
                        )

                    services._record_error("Test operation", "Test failure")
                    await pilot.pause()
                    error_button = services.query_one("#view-error", Button)
                    self.assertTrue(error_button.display)
                    self.assertEqual(error_button.region.height, 3)
                    screenshot = ET.fromstring(app.export_screenshot())
                    self.assertIn(
                        "View error details", "".join(screenshot.itertext()).replace("\xa0", " ")
                    )

    async def test_service_info_action_renders_catalog_metadata(self) -> None:
        manager = FakeDockerManager()
        manager.catalog = [
            ComposeService(
                name="sample",
                status="Up",
                state="running",
                category="Motion",
                execution_type="service",
                source_compose="docker/deploy/compose.motion.yaml",
                image="ghcr.io/example/motion:jazzy",
                command="ros2 launch example.launch.py",
                environment_variables=("LEADER_PORT", "LEADER_DOF"),
                dockerfile="docker/motion/Dockerfile",
                documentation="docs/usage.md",
            )
        ]
        app = ServicesTestApp(manager)

        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            await pilot.click("#service-info")
            await pilot.pause()

            self.assertIsInstance(app.screen, ServiceInfoScreen)
            details = app.screen.query_one("#service-information-content").query_one(Static)
            self.assertIsInstance(
                app.screen.query_one("#service-information-content"), VerticalScroll
            )
            rendered = details.render().plain
            for value in (
                "sample",
                "Persistent service",
                "docker/deploy/compose.motion.yaml",
                "ghcr.io/example/motion:jazzy",
                "ros2 launch example.launch.py",
                "LEADER_PORT, LEADER_DOF",
                "docker/motion/Dockerfile",
                "docs/usage.md",
            ):
                self.assertIn(value, rendered)
            self.assertEqual(manager.calls, [])
            self.assertEqual(manager.tool_calls, [])

    async def test_calibration_configuration_validates_path_and_confirms_overwrite(self) -> None:
        manager = FakeDockerManager()
        app = ServicesTestApp(manager)
        host_root = Path("/host/deploy/config/calibration")

        def resolve_path(value: str) -> Path:
            if not value.startswith("/config/calibration/"):
                raise ValueError("Path must be under /config/calibration.")
            return host_root / value.removeprefix("/config/calibration/")

        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            configuration = ToolConfigurationScreen(
                "lerobot-calibrate-leader",
                ToolMetadata(
                    "interactive",
                    ("LEADER_CALIBRATION_FILE",),
                    may_overwrite_calibration=True,
                ),
                {"LEADER_CALIBRATION_FILE": "/config/calibration/5dof/leader.yaml"},
                calibration_files=[
                    ("/config/calibration/5dof/leader.yaml", "/config/calibration/5dof/leader.yaml")
                ],
                calibration_directories=[
                    ("/config/calibration/custom", "/config/calibration/custom")
                ],
                calibration_path_resolver=resolve_path,
            )
            app.push_screen(configuration)
            await pilot.pause()

            input_widget = app.screen.query_one("#config-LEADER_CALIBRATION_FILE", Input)
            input_widget.value = "/outside/calibration.yaml"
            await pilot.pause()
            await pilot.click("#save-tool-config")
            await pilot.pause()
            self.assertIsInstance(app.screen, ToolConfigurationScreen)
            self.assertTrue(app.screen.query_one("#tool-config-error", Static).display)

            input_widget = app.screen.query_one("#config-LEADER_CALIBRATION_FILE", Input)
            input_widget.value = "/config/calibration/custom/leader.yaml"
            await pilot.pause()
            self.assertIn(
                "/host/deploy/config/calibration/custom/leader.yaml",
                app.screen.query_one("#calibration-host-LEADER_CALIBRATION_FILE", Static)
                .render()
                .plain,
            )
            await pilot.click("#save-tool-config")
            await pilot.pause()

            app.push_screen(
                ToolExecutionConfirmation(
                    "lerobot-calibrate-leader",
                    [],
                    interactive=True,
                    may_overwrite_calibration=True,
                    calibration_overwrite_path=(
                        "/host/deploy/config/calibration/custom/leader.yaml"
                    ),
                )
            )
            await pilot.pause()
            warning = "".join(ET.fromstring(app.export_screenshot()).itertext()).replace(
                "\xa0", " "
            )
            self.assertIn("overwrite the existing file", warning)
            self.assertIn(
                "/host/deploy/config/calibration/custom/leader.yaml",
                warning,
            )

    async def test_tool_requires_configured_hardware_path(self) -> None:
        manager = FakeDockerManager()
        manager.catalog = [
            ComposeService(
                "hiwonder-scan-leader",
                "Not created",
                "not created",
                "Tools",
                "one-shot",
            )
        ]
        app = ServicesTestApp(manager)

        async with app.run_test() as pilot:
            await pilot.pause()
            services = app.query_one(ServicesView)
            services._set_category("Tools")
            await pilot.pause()
            services.action_run_tool()
            await pilot.pause()

            self.assertEqual(manager.tool_calls, [])
            self.assertIn(
                "Configure LEADER_PORT",
                str(services.query_one("#operation-status").render()),
            )

    async def test_one_shot_failure_reports_exit_code_and_captured_error(self) -> None:
        manager = FakeDockerManager()
        manager.catalog = [
            ComposeService(
                "hiwonder-scan-leader",
                "Not created",
                "not created",
                "Tools",
                "one-shot",
            )
        ]
        manager.environment["LEADER_PORT"] = "/dev/null"
        manager.tool_result = ToolExecutionResult(17, "", "serial port unavailable")
        app = ServicesTestApp(manager)

        async with app.run_test(size=(100, 32)) as pilot:
            services = app.query_one(ServicesView)
            services._set_category("Tools")
            await pilot.pause()
            await pilot.click("#run-tool")
            await pilot.pause()
            await pilot.click("#confirm-tool")
            await pilot.pause()
            await pilot.pause()

            self.assertIsInstance(app.screen, ToolOutputScreen)
            self.assertEqual(app.screen.exit_code, 17)
            self.assertEqual(app.screen.stderr, "serial port unavailable")
            self.assertIn("exit code 17", str(services.query_one("#operation-status").render()))

    async def test_compose_catalog_remains_visible_when_daemon_is_unavailable(self) -> None:
        manager = FakeDockerManager()
        manager.status_error = "daemon is unavailable"
        manager.catalog = [
            ComposeService("sample", "Not created", "not created", "Motion", "service")
        ]
        app = ServicesTestApp(manager)

        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one(ServiceTable)

            self.assertEqual(table.row_count, 1)
            self.assertEqual(table.get_selected_service(), "sample")
            self.assertEqual(table.get_cell("sample", "state"), "unavailable")
            self.assertEqual(table.get_cell("sample", "category"), "Motion")

    async def test_interactive_tool_requires_a_real_terminal(self) -> None:
        manager = FakeDockerManager()
        manager.catalog = [
            ComposeService(
                "lerobot-calibrate-leader",
                "Not created",
                "not created",
                "Calibration",
                "interactive",
            )
        ]
        app = ServicesTestApp(manager)

        async with app.run_test() as pilot:
            await pilot.pause()
            services = app.query_one(ServicesView)
            services._set_category("Calibration")
            await pilot.pause()
            services.action_run_interactive_tool()
            await pilot.pause()

            self.assertIn(
                "require a real terminal",
                str(services.query_one("#operation-status").render()),
            )

    async def test_interactive_terminal_is_restored_after_completion_and_failure(self) -> None:
        manager = FakeDockerManager()
        manager.catalog = [
            ComposeService(
                "lerobot-calibrate-leader",
                "Not created",
                "not created",
                "Calibration",
                "interactive",
            )
        ]
        manager.environment["LEADER_PORT"] = "/dev/null"
        app = ServicesTestApp(manager)
        tty_stream = unittest.mock.Mock()
        tty_stream.isatty.return_value = True

        async with app.run_test() as pilot:
            services = app.query_one(ServicesView)
            services._set_category("Calibration")
            await pilot.pause()

            for error, interrupted, exit_code in (
                (None, False, 0),
                ("Docker daemon disconnected", False, 0),
                (None, True, 0),
                (None, False, 130),
            ):
                manager.interactive_error = error
                manager.interactive_interrupt = interrupted
                manager.interactive_cancel = False
                manager.interactive_exit_code = exit_code
                suspension = unittest.mock.MagicMock()
                with (
                    patch("lerobot_tui.widgets.services_view.sys.stdin", tty_stream),
                    patch("lerobot_tui.widgets.services_view.sys.stdout", tty_stream),
                    patch("lerobot_tui.widgets.services_view.sys.stderr", tty_stream),
                    patch.object(app, "suspend", return_value=suspension),
                ):
                    services.action_run_interactive_tool()
                    await pilot.pause()
                    self.assertIsInstance(app.screen, ToolExecutionConfirmation)
                    await pilot.click("#confirm-tool")
                    await pilot.pause()
                    await pilot.pause()

                suspension.__enter__.assert_called_once()
                suspension.__exit__.assert_called_once()
                self.assertIsNone(suspension.__exit__.call_args.args[0])
                self.assertTrue(services.is_mounted)
                self.assertEqual(services.query_one("#operation-progress").display, False)
                status = str(services.query_one("#operation-status").render())
                if interrupted:
                    self.assertIn("Cancelled", status)
                elif exit_code == 130:
                    self.assertIn("failed with exit code 130", status)
                elif error:
                    self.assertIn("Failed", status)
                else:
                    self.assertIn("exit code 0", status)

            manager.interactive_error = None
            manager.interactive_interrupt = False
            manager.interactive_cancel = True
            suspension = unittest.mock.MagicMock()
            with (
                patch("lerobot_tui.widgets.services_view.sys.stdin", tty_stream),
                patch("lerobot_tui.widgets.services_view.sys.stdout", tty_stream),
                patch("lerobot_tui.widgets.services_view.sys.stderr", tty_stream),
                patch.object(app, "suspend", return_value=suspension),
            ):
                services.action_run_interactive_tool()
                await pilot.pause()
                await pilot.click("#confirm-tool")
                await pilot.pause()

            suspension.__enter__.assert_called_once()
            suspension.__exit__.assert_called_once()
            self.assertTrue(services.is_mounted)
            self.assertEqual(len(manager.interactive_calls), 5)


if __name__ == "__main__":
    unittest.main()
