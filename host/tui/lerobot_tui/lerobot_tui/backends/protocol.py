from typing import Protocol

from lerobot_tui.models import RobotInfo, SystemInfo


class DashboardBackend(Protocol):
    def get_system_info(self) -> SystemInfo: ...

    def get_robots(self) -> list[RobotInfo]: ...
