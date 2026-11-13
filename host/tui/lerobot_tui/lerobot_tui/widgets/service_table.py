from textual.widgets import DataTable

from lerobot_tui.backends.docker import ComposeService


class ServiceTable(DataTable):
    def on_mount(self) -> None:
        self.cursor_type = "row"

        self.add_column("Service", key="service")
        self.add_column("State", key="state")
        self.add_column("Status", key="status")

    def update_services(
        self,
        services: list[ComposeService],
    ) -> None:
        services_by_name = {service.name: service for service in services}
        selected_service = self.get_selected_service()
        existing_names = {str(row_key.value) for row_key in self.rows}

        for name in existing_names - services_by_name.keys():
            self.remove_row(name)

        for service in sorted(services, key=lambda item: item.name):
            if service.name not in existing_names:
                self.add_row(
                    service.name,
                    service.state,
                    service.status,
                    key=service.name,
                )
                continue

            if self.get_cell(service.name, "state") != service.state:
                self.update_cell(service.name, "state", service.state)
            if self.get_cell(service.name, "status") != service.status:
                self.update_cell(service.name, "status", service.status)

        if selected_service in services_by_name:
            self.move_cursor(
                row=self.get_row_index(selected_service),
                column=0,
                animate=False,
            )

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
            if self.get_cell(service, "state") != "unavailable":
                self.update_cell(service, "state", "unavailable")
            if self.get_cell(service, "status") != "Unavailable":
                self.update_cell(service, "status", "Unavailable")
