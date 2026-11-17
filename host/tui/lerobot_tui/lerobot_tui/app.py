import os
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.widgets import (
    Button,
    Footer,
    OptionList,
    Static,
    TabbedContent,
    TabPane,
)

from lerobot_tui.backends.docker import DockerCompose
from lerobot_tui.backends.system import SystemInfoBackend
from lerobot_tui.models import SystemInfo
from lerobot_tui.widgets.dashboard_view import DASHBOARD_LOGO, DashboardView
from lerobot_tui.widgets.robot_table import ROBOT_LOGO
from lerobot_tui.widgets.service_table import SERVICE_LOGO, ServiceTable
from lerobot_tui.widgets.services_view import ServicesView
from lerobot_tui.widgets.settings_view import SettingsView

WIFI_LOGO = r"""
 _       ________________
| |     / /  _/ ____/  _/
| | /| / // // /_   / /  
| |/ |/ // // __/ _/ /   
|__/|__/___/_/   /___/   
""".strip("\n")


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
        self._docker: DockerCompose | None = None
        self._startup_error: str | None = None

        try:
            compose_file = self._compose_file()
            self._docker = DockerCompose(compose_file)
        except (FileNotFoundError, ValueError) as exc:
            self._startup_error = str(exc)

        self._backend = SystemInfoBackend(
            self._docker.directory if self._docker is not None else None
        )

    def compose(self) -> ComposeResult:
        with TabbedContent(initial="dashboard", id="main-tabs"):
            with TabPane("1 Dashboard", id="dashboard"):
                yield Static(
                    DASHBOARD_LOGO,
                    id="dashboard-logo",
                    markup=False,
                )
                yield DashboardView()

            with TabPane("2 Services", id="services"):
                yield Static(
                    SERVICE_LOGO,
                    id="services-logo",
                    markup=False,
                )
                yield ServicesView(self._docker, self._startup_error)

            with TabPane("3 Robots", id="robots"):
                yield Static(
                    ROBOT_LOGO,
                    id="robots-logo",
                    markup=False,
                )
                yield Static(
                    "Robot information is unavailable until the robot interface is connected."
                )

            with TabPane("4 WiFi", id="wifi"):
                yield Static(
                    WIFI_LOGO,
                    id="wifi-logo",
                    markup=False,
                )
                yield Static("WiFi management is not available yet.")

            with TabPane("5 Settings", id="settings"):
                if self._docker is not None:
                    yield SettingsView(self._docker.directory)
                else:
                    yield Static(
                        "Configuration directory unavailable.",
                        classes="section-title",
                    )

        yield Footer()

    def on_mount(self) -> None:
        self.update_system_info(self._backend.get_system_info())
        self.set_interval(2.0, lambda: self.update_system_info(self._backend.get_system_info()))

        self._update_docker_stats()
        self.set_interval(5.0, self._update_docker_stats)

        if self._startup_error:
            self.notify(
                f"Cannot load deployment Compose configuration: {self._startup_error}",
                severity="error",
            )

        if self._docker is not None and not self._backend.env_file_exists:
            self.notify(
                f"Environment file not found: {self._docker.directory / '.env'}",
                title="Missing Docker Environment",
                severity="warning",
                timeout=10,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "open-services":
            self.query_one(TabbedContent).active = "services"

    def on_services_view_updated(self, event: ServicesView.Updated) -> None:
        dashboard = self.query_one(DashboardView)
        dashboard.update_docker_status(event.services, event.connected)

    def action_show_dashboard(self) -> None:
        self._switch_tab("dashboard")

    def action_show_services(self) -> None:
        self._switch_tab("services")

    def action_show_robots(self) -> None:
        self._switch_tab("robots")

    def action_show_wifi(self) -> None:
        self._switch_tab("wifi")

    def action_show_settings(self) -> None:
        self._switch_tab("settings")

    def update_system_info(self, info: SystemInfo) -> None:
        self.query_one("#system-summary", Static).update(
            f"CPU: {info.cpu_percent:.0f}%    "
            f"RAM: {info.memory_percent:.0f}% "
            f"({info.memory_used_gb:.1f}/{info.memory_total_gb:.1f} GiB)"
        )

        if info.env_file_exists:
            ros_info = f"ROS2: Jazzy    RMW: {info.rmw}"
        else:
            ros_info = "[yellow]⚠ Missing docker/deploy/.env[/yellow]"

        self.query_one("#ros-summary", Static).update(ros_info)

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

    def _switch_tab(self, tab_id: str) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)

        if tabs.active == tab_id:
            return

        # Move focus away from the currently active tab.
        self.set_focus(None)

        # Activate the requested tab.
        tabs.active = tab_id

        # Focus the primary widget after the tab switch.
        def focus_tab() -> None:
            if tabs.active != tab_id:
                return

            if tab_id == "services":
                self.query_one(ServiceTable).focus()

            elif tab_id == "settings":
                self.query_one("#settings-files", OptionList).focus()

        self.call_after_refresh(focus_tab)

    @work(group="docker-stats", exclusive=True)
    async def _update_docker_stats(self) -> None:
        if self._docker is None:
            return

        try:
            stats = await self._docker.stats()
            self.query_one(DashboardView).update_docker_stats(stats)
        except Exception:
            self.query_one("#docker-stats", Static).update("Docker statistics unavailable.")
