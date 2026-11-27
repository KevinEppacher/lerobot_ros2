from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Static

from lerobot_tui.models import SystemInfo

DASHBOARD_LOGO = r"""
    __         ____        __          __  ____  ____  ________ 
   / /   ___  / __ \____  / /_  ____  / /_/ __ \/ __ \/ ___/__ \
  / /   / _ \/ /_/ / __ \/ __ \/ __ \/ __/ /_/ / / / /\__ \__/ /
 / /___/  __/ _, _/ /_/ / /_/ / /_/ / /_/ _, _/ /_/ /___/ / __/ 
/_____/\___/_/ |_|\____/_.___/\____/\__/_/ |_|\____//____/____/ 
   / __ \____ ______/ /_  / /_  ____  ____ __________/ /        
  / / / / __ `/ ___/ __ \/ __ \/ __ \/ __ `/ ___/ __  /         
 / /_/ / /_/ (__  ) / / / /_/ / /_/ / /_/ / /  / /_/ /          
/_____/\__,_/____/_/ /_/_.___/\____/\__,_/_/   \__,_/           
""".strip("\n")


class DashboardView(VerticalScroll):
    def compose(self) -> ComposeResult:
        with Vertical(classes="dashboard-panel"):
            yield Static("SYSTEM", classes="section-title")
            yield Static("CPU: --    RAM: --", id="system-summary")
            yield Static("ROS2: --    RMW: --", id="ros-summary")
            yield Static("Docker: Checking…", id="docker-connection")

        with Vertical(classes="dashboard-panel"):
            yield Static("DOCKER SERVICES", classes="section-title")
            yield Static(
                "Running: --    Stopped: --    Not created: --",
                id="service-summary",
            )
            with Horizontal(classes="dashboard-actions"):
                yield Button(
                    "Open Services",
                    id="open-services",
                    variant="primary",
                )

        with Vertical(classes="dashboard-panel"):
            yield Static("DOCKER RESOURCES", classes="section-title")
            yield Static(
                "Loading container statistics...",
                id="docker-stats",
            )

    def update_system_info(self, info: SystemInfo) -> None:
        self.query_one("#system-summary", Static).update(
            f"CPU: {info.cpu_percent:.0f}%    "
            f"RAM: {info.memory_percent:.0f}% "
            f"({info.memory_used_gb:.1f}/{info.memory_total_gb:.1f} GiB)"
        )
        self.query_one("#ros-summary", Static).update(f"ROS2: {info.ros_distro}    RMW: {info.rmw}")

    def update_docker_status(
        self,
        services: dict[str, str],
        connected: bool,
    ) -> None:
        connection = "Connected" if connected else "Unavailable"

        self.query_one("#docker-connection", Static).update(f"Docker: {connection}")

        if not connected:
            summary = "Running: --    Stopped: --    Not created: --"
        else:
            running = sum(state == "running" for state in services.values())
            not_created = sum(state == "not created" for state in services.values())
            stopped = len(services) - running - not_created

            summary = f"Running: {running}    Stopped: {stopped}    Not created: {not_created}"

        self.query_one("#service-summary", Static).update(summary)

    def update_docker_stats(self, stats: list[dict[str, str]]) -> None:
        if not stats:
            self.query_one("#docker-stats", Static).update("No running containers.")
            return

        lines = [
            f"{'CONTAINER':<32} {'CPU':>10} {'MEMORY':>24}",
            "-" * 68,
        ]

        for container in sorted(stats, key=lambda item: item.get("Name", "")):
            name = container.get("Name", "unknown")
            cpu = container.get("CPUPerc", "--")
            memory = container.get("MemUsage", "--")

            lines.append(f"{name[:32]:<32} {cpu:>10} {memory:>24}")

        self.query_one("#docker-stats", Static).update("\n".join(lines))
