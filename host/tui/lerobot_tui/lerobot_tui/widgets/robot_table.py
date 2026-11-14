r"""
    __         ____        __          __  ____  ____  ________ 
   / /   ___  / __ \____  / /_  ____  / /_/ __ \/ __ \/ ___/__ \
  / /   / _ \/ /_/ / __ \/ __ \/ __ \/ __/ /_/ / / / /\__ \__/ /
 / /___/  __/ _, _/ /_/ / /_/ / /_/ / /_/ _, _/ /_/ /___/ / __/ 
/_____/\___/_/ |_|\____/_.___/\____/\__/_/ |_|\____//____/____/ 
   / __ \____  / /_  ____  / /______                            
  / /_/ / __ \/ __ \/ __ \/ __/ ___/                            
 / _, _/ /_/ / /_/ / /_/ / /_(__  )                             
/_/ |_|\____/_.___/\____/\__/____/                              
"""

from textual.widgets import DataTable

from lerobot_tui.models import RobotInfo

ROBOT_LOGO = (__doc__ or "").strip("\n")


class RobotTable(DataTable):
    def on_mount(self) -> None:
        self.cursor_type = "row"

        self.add_columns(
            "Namespace",
            "Model",
            "DOF",
            "Mode",
            "Status",
        )

    def update_robots(self, robots: list[RobotInfo]) -> None:
        self.clear()

        for robot in robots:
            self.add_row(
                robot.namespace,
                robot.model,
                str(robot.dof),
                robot.mode.value,
                "Connected" if robot.connected else "Offline",
                key=robot.namespace,
            )
