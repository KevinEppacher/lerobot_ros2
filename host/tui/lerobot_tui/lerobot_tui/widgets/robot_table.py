from textual.widgets import DataTable

from lerobot_tui.models import RobotInfo


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
