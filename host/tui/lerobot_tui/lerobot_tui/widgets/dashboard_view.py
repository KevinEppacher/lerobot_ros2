from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from lerobot_tui.backends.docker import ComposeService
from lerobot_tui.models import SystemInfo


class DashboardView(Vertical):
    def compose(self) -> ComposeResult:
        with Vertical(classes="dashboard-panel"):
            yield Static("SYSTEM", classes="section-title")
            yield Static("CPU: --    RAM: --", id="system-summary")
            yield Static("Docker: Checking…", id="docker-connection")

        with Vertical(classes="dashboard-panel"):
            yield Static("ROBOTS", classes="section-title")
            yield Static(
                "Robot information is unavailable until the robot interface is connected.",
                id="robot-summary",
            )

        with Vertical(classes="dashboard-panel"):
            yield Static("DOCKER SERVICES", classes="section-title")
            yield Static("Running: --    Stopped: --    Failed: --", id="service-summary")
            with Horizontal(classes="dashboard-actions"):
                yield Button("Open Services", id="open-services", variant="primary")

    def update_system_info(self, info: SystemInfo) -> None:
        self.query_one("#system-summary", Static).update(
            f"CPU: {info.cpu_percent:.0f}%    "
            f"RAM: {info.memory_percent:.0f}% "
            f"({info.memory_used_gb:.1f}/{info.memory_total_gb:.1f} GiB)"
        )

    def update_docker_status(
        self,
        services: list[ComposeService],
        connected: bool,
    ) -> None:
        connection = "Connected" if connected else "Unavailable"
        self.query_one("#docker-connection", Static).update(f"Docker: {connection}")
        if not connected:
            summary = "Running: --    Stopped: --    Failed: --"
        else:
            running = sum(service.state.lower() == "running" for service in services)
            failed = sum(
                service.state.lower() in {"dead", "error", "failed"} for service in services
            )
            stopped = len(services) - running - failed
            summary = f"Running: {running}    Stopped: {stopped}    Failed: {failed}"
        self.query_one("#service-summary", Static).update(summary)
