from rich.text import Text
from textual.widgets import DataTable

from lerobot_tui.backends.docker import ALL_SERVICES, SERVICES

SERVICE_LOGO = r"""
   _____                 _
  / ___/___  ______   __(_)_______  _____
  \__ \/ _ \/ ___/ | / / / ___/ _ \/ ___/
 ___/ /  __/ /   | |/ / / /__/  __(__  )
/____/\___/_/    |___/_/\___/\___/____/
""".strip("\n")


class ServiceTable(DataTable):
    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True

        self.add_column("Service", key="service")
        self.add_column("●", key="indicator")
        self.add_column("State", key="state")

        self.show_category(
            "All",
            {service: "not created" for service in ALL_SERVICES},
        )

    def update_services(self, services: dict[str, str]) -> None:
        for row_key in self.rows:
            service = str(row_key.value)
            state = services.get(service, "not created")

            self.update_cell(
                row_key,
                "indicator",
                self._indicator(state),
                update_width=False,
            )
            self.update_cell(
                row_key,
                "state",
                state,
                update_width=False,
            )

    def get_selected_service(self) -> str | None:
        if self.row_count == 0 or self.cursor_row < 0:
            return None

        row_key = self.coordinate_to_cell_key((self.cursor_row, 0)).row_key

        return str(row_key.value)

    @staticmethod
    def _indicator(state: str) -> Text:
        colors = {
            "running": "green",
            "exited": "yellow",
            "stopped": "yellow",
            "not created": "grey35",
            "unavailable": "red",
        }

        return Text("●", style=colors.get(state.lower(), "red"))

    def show_category(self, category: str, states: dict[str, str]) -> None:
        self.clear()

        services = ALL_SERVICES if category == "All" else SERVICES[category]

        for service in services:
            state = states.get(service, "not created")

            self.add_row(
                service,
                self._indicator(state),
                state,
                key=service,
            )
