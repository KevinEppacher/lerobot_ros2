import os
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Button, Footer, Header, Static, TabbedContent, TabPane

from lerobot_tui.backends.docker import DockerComposeManager
from lerobot_tui.backends.mock import MockDashboardBackend
from lerobot_tui.widgets.dashboard_view import DashboardView
from lerobot_tui.widgets.services_view import ServicesView


class LeRobotApp(App[None]):
    TITLE = "LeRobot Setup"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("1", "show_dashboard", "Dashboard"),
        ("2", "show_services", "Services"),
        ("3", "show_robots", "Robots"),
        ("4", "show_wifi", "WiFi"),
        ("5", "show_settings", "Settings"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._backend = MockDashboardBackend()
        self._docker: DockerComposeManager | None = None
        self._startup_error: str | None = None
        try:
            self._docker = DockerComposeManager(compose_file=self._compose_file())
        except (FileNotFoundError, ValueError) as exc:
            self._startup_error = str(exc)

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="dashboard", id="main-tabs"):
            yield TabPane("1 Dashboard", DashboardView(), id="dashboard")
            yield TabPane(
                "2 Services",
                ServicesView(self._docker, self._startup_error),
                id="services",
            )
            yield TabPane(
                "3 Robots",
                Static(
                    "Robot information is unavailable until the robot interface is connected.",
                    classes="placeholder-view",
                ),
                id="robots",
            )
            yield TabPane(
                "4 WiFi",
                Static("WiFi management is not available yet.", classes="placeholder-view"),
                id="wifi",
            )
            yield TabPane(
                "5 Settings",
                Static("Settings are not available yet.", classes="placeholder-view"),
                id="settings",
            )
        yield Footer()

    def on_mount(self) -> None:
        self._update_system_info()
        self.set_interval(2.0, self._update_system_info)
        if self._startup_error:
            self.notify(
                f"Cannot load deployment Compose configuration: {self._startup_error}",
                severity="error",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-services":
            self.query_one(TabbedContent).active = "services"

    def on_services_view_updated(self, event: ServicesView.Updated) -> None:
        dashboard = self.query_one(DashboardView)
        dashboard.update_docker_status(event.services, event.connected)

    def action_show_dashboard(self) -> None:
        self.query_one(TabbedContent).active = "dashboard"

    def action_show_services(self) -> None:
        self.query_one(TabbedContent).active = "services"

    def action_show_robots(self) -> None:
        self.query_one(TabbedContent).active = "robots"

    def action_show_wifi(self) -> None:
        self.query_one(TabbedContent).active = "wifi"

    def action_show_settings(self) -> None:
        self.query_one(TabbedContent).active = "settings"

    def _update_system_info(self) -> None:
        self.query_one(DashboardView).update_system_info(self._backend.get_system_info())

    @staticmethod
    def _compose_file() -> Path:
        configured_path = os.environ.get("LEROBOT_COMPOSE_FILE")
        if configured_path:
            return Path(configured_path)

        search_roots = [Path.cwd(), *Path(__file__).resolve().parents]
        for root in search_roots:
            candidate = root / "docker" / "deploy" / "compose.yaml"
            if candidate.is_file():
                return candidate

        raise FileNotFoundError(
            "Deployment Compose file not found. Set LEROBOT_COMPOSE_FILE to "
            "docker/deploy/compose.yaml."
        )
