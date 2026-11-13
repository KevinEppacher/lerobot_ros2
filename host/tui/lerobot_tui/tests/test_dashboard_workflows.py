import asyncio
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from lerobot_tui.app import LeRobotApp
from lerobot_tui.backends.docker import ComposeService, DockerComposeError
from lerobot_tui.screens.operation_error import OperationErrorScreen
from lerobot_tui.screens.service_logs import ServiceLogsScreen
from lerobot_tui.screens.update_confirmation import UpdateConfirmation
from lerobot_tui.widgets.dashboard_view import DashboardView
from lerobot_tui.widgets.service_table import ServiceTable
from lerobot_tui.widgets.services_view import ServicesView
from textual.app import App, ComposeResult
from textual.widgets import Header, TabbedContent, TabPane


class FakeDockerManager:
    def __init__(self, state: str = "running") -> None:
        self.state = state
        self.calls: list[str] = []
        self.error: str | None = None
        self.wait_for_start = False
        self.start_started = asyncio.Event()
        self.release_start = asyncio.Event()

    async def get_services(self) -> list[str]:
        return ["sample"]

    async def get_status(self) -> list[ComposeService]:
        if self.state == "not created":
            return []
        return [ComposeService("sample", self.state, self.state)]

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
    async def test_host_application_has_all_tabs_and_number_navigation(self) -> None:
        manager = FakeDockerManager()
        compose_file = Path(__file__).resolve().parents[4] / "docker" / "deploy" / "compose.yaml"
        with (
            patch.dict(os.environ, {"LEROBOT_COMPOSE_FILE": str(compose_file)}),
            patch("lerobot_tui.app.DockerComposeManager", return_value=manager),
        ):
            app = LeRobotApp()
            async with app.run_test() as pilot:
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

    async def test_dashboard_summarizes_service_states(self) -> None:
        manager = FakeDockerManager("running")
        app = ServicesTestApp(manager)

        async with app.run_test() as pilot:
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


if __name__ == "__main__":
    unittest.main()
