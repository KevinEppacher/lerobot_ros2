from textual.widgets import Static

from lerobot_tui.models import SystemInfo


class SystemPanel(Static):
    def update_info(self, info: SystemInfo) -> None:
        self.update(
            f"[b]Host:[/b] {info.hostname}\n"
            f"[b]ROS:[/b] {info.ros_distro}\n"
            f"[b]RMW:[/b] {info.rmw}\n"
            f"[b]CPU:[/b] {info.cpu_percent:.1f}%\n"
            f"[b]RAM:[/b] {info.memory_percent:.1f}% "
            f"({info.memory_used_gb:.1f}/{info.memory_total_gb:.1f} GiB)"
        )
