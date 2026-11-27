import socket
from pathlib import Path

import psutil

from lerobot_tui.models import SystemInfo


class SystemInfoBackend:
    def __init__(self, compose_directory: Path | None = None) -> None:
        self._env_file = compose_directory / ".env" if compose_directory is not None else None
        self._env_file_exists = self._env_file is not None and self._env_file.is_file()

    def _get_env_value(self, key: str) -> str:
        if not self._env_file_exists:
            return "unknown"

        try:
            for line in self._env_file.read_text().splitlines():
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                if line.startswith("export "):
                    line = line.removeprefix("export ").strip()

                name, separator, value = line.partition("=")

                if separator and name.strip() == key:
                    value = value.strip()

                    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                        value = value[1:-1]

                    return value or "unknown"

        except OSError:
            return "unknown"

        return "unknown"

    def get_system_info(self) -> SystemInfo:
        memory = psutil.virtual_memory()
        return SystemInfo(
            hostname=socket.gethostname(),
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=memory.percent,
            memory_used_gb=memory.used / (1024**3),
            memory_total_gb=memory.total / (1024**3),
            rmw=self._get_env_value("RMW_IMPLEMENTATION"),
            ros_distro=self._get_env_value("ROS_DISTRO"),
            env_file_exists=self.env_file_exists,
        )

    @property
    def env_file_exists(self) -> bool:
        return self._env_file is not None and self._env_file.is_file()
