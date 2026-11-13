from dataclasses import dataclass
from enum import Enum


class RobotMode(str, Enum):
    IDLE = "IDLE"
    TELEOP = "TELEOP"
    MANIPULATION = "MANIPULATION"


@dataclass(frozen=True, slots=True)
class RobotInfo:
    namespace: str
    model: str
    dof: int
    mode: RobotMode
    connected: bool


@dataclass(frozen=True, slots=True)
class SystemInfo:
    hostname: str
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    rmw: str
    ros_distro: str
