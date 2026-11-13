import os
import socket

import psutil

from lerobot_tui.models import RobotInfo, SystemInfo


class MockDashboardBackend:
    def get_system_info(self) -> SystemInfo:
        memory = psutil.virtual_memory()

        return SystemInfo(
            hostname=socket.gethostname(),
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=memory.percent,
            memory_used_gb=memory.used / (1024**3),
            memory_total_gb=memory.total / (1024**3),
            rmw=os.getenv("RMW_IMPLEMENTATION", "unknown"),
            ros_distro=os.getenv("ROS_DISTRO", "unknown"),
        )

    def get_robots(self) -> list[RobotInfo]:
        return []
