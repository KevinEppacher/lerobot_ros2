r"""
    __         ____        __          __  ____  ____  ________ 
   / /   ___  / __ \____  / /_  ____  / /_/ __ \/ __ \/ ___/__ \
  / /   / _ \/ /_/ / __ \/ __ \/ __ \/ __/ /_/ / / / /\__ \__/ /
 / /___/  __/ _, _/ /_/ / /_/ / /_/ / /_/ _, _/ /_/ /___/ / __/ 
/_____/\___/_/ |_|\____/_.___/\____/\__/_/ |_|\____//____/____/ 
   _____                 _                                      
  / ___/___  ______   __(_)_______  _____                       
  \__ \/ _ \/ ___/ | / / / ___/ _ \/ ___/                       
 ___/ /  __/ /   | |/ / / /__/  __(__  )                        
/____/\___/_/    |___/_/\___/\___/____/                         
"""

from rich.text import Text
from textual.widgets import DataTable

from lerobot_tui.backends.docker import ComposeService

SERVICE_LOGO = (__doc__ or "").strip("\n")


class ServiceTable(DataTable):
    def on_mount(self) -> None:
        self.cursor_type = "row"
        self._service_states: dict[str, str] = {}

        self.add_column("Service", key="service")
        self.add_column("●", key="indicator")
        self.add_column("State", key="state")
        self.add_column("Status", key="status")
        self.add_column("Category", key="category")

    def update_services(
        self,
        services: list[ComposeService],
        preferred_service: str | None = None,
    ) -> None:
        services_by_name = {service.name: service for service in services}
        selected_service = preferred_service or self.get_selected_service()
        existing_names = {str(row_key.value) for row_key in self.rows}

        for name in existing_names - services_by_name.keys():
            self.remove_row(name)
            self._service_states.pop(name, None)

        for service in sorted(services, key=lambda item: item.name):
            self._service_states[service.name] = service.state
            if service.name not in existing_names:
                self.add_row(
                    service.name,
                    self._status_indicator(service.state),
                    service.state,
                    service.status,
                    service.category,
                    key=service.name,
                )
                continue

            for column, value in (
                ("indicator", self._status_indicator(service.state)),
                ("state", service.state),
                ("status", service.status),
                ("category", service.category),
            ):
                if self.get_cell(service.name, column) != value:
                    self.update_cell(service.name, column, value)

        self.sort("service", key=self._sort_key)

        target_service = (
            selected_service
            if selected_service in services_by_name
            else next(iter(services_by_name), None)
        )
        if target_service is not None:
            self.move_cursor(
                row=self.get_row_index(target_service),
                column=0,
                animate=False,
            )

    def _sort_key(self, value: object) -> tuple[int, str, str]:
        service = str(value)
        state = self._service_states.get(service, "unknown").lower()
        priority = 0 if state == "running" else 2 if state == "not created" else 1
        return priority, state, service.lower()

    @staticmethod
    def _status_indicator(state: str) -> Text:
        colors = {
            "running": "green",
            "stopped": "red",
            "exited": "grey70",
            "not created": "grey23",
        }
        return Text("●", style=colors.get(state.lower(), "white"))

    def get_selected_service(self) -> str | None:
        if self.row_count == 0:
            return None

        if self.cursor_row < 0:
            return None

        row_key = self.coordinate_to_cell_key((self.cursor_row, 0)).row_key

        return str(row_key.value)

    def get_service_state(self, service: str) -> str | None:
        if service not in {str(row_key.value) for row_key in self.rows}:
            return None
        return str(self.get_cell(service, "state"))

    def mark_unavailable(self) -> None:
        for row_key in self.rows:
            service = str(row_key.value)
            self._service_states[service] = "unavailable"
            indicator = self._status_indicator("unavailable")
            if self.get_cell(service, "indicator") != indicator:
                self.update_cell(service, "indicator", indicator)
            if self.get_cell(service, "state") != "unavailable":
                self.update_cell(service, "state", "unavailable")
            if self.get_cell(service, "status") != "Unavailable":
                self.update_cell(service, "status", "Unavailable")
        self.sort("service", key=self._sort_key)
