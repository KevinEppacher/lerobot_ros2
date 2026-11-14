r"""
    __         ____        __          __  ____  ____  ________ 
   / /   ___  / __ \____  / /_  ____  / /_/ __ \/ __ \/ ___/__ \
  / /   / _ \/ /_/ / __ \/ __ \/ __ \/ __/ /_/ / / / /\__ \__/ /
 / /___/  __/ _, _/ /_/ / /_/ / /_/ / /_/ _, _/ /_/ /___/ / __/ 
/_____/\___/_/_|_|\____/_.___/\____/\__/_/ |_|\____//____/____/ 
  / ___/___  / /_/ /_(_)___  ____ ______                        
  \__ \/ _ \/ __/ __/ / __ \/ __ `/ ___/                        
 ___/ /  __/ /_/ /_/ / / / / /_/ (__  )                         
/____/\___/\__/\__/_/_/ /_/\__, /____/                          
                          /____/                                
"""

from textual.widgets import Static

from lerobot_tui.models import SystemInfo

SYSTEM_LOGO = (__doc__ or "").strip("\n")


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
