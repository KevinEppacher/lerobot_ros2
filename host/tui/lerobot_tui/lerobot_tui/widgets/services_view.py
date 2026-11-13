from collections.abc import Awaitable, Callable

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, DataTable, LoadingIndicator, Static

from lerobot_tui.backends.docker import (
    ComposeService,
    DockerComposeError,
    DockerComposeManager,
)
from lerobot_tui.screens.operation_error import OperationErrorScreen
from lerobot_tui.screens.service_logs import ServiceLogsScreen
from lerobot_tui.screens.update_confirmation import UpdateConfirmation
from lerobot_tui.widgets.service_table import ServiceTable


class ServicesView(Widget):
    BINDINGS = [
        ("s", "start_service", "Start service"),
        ("x", "stop_service", "Stop service"),
        ("r", "restart_service", "Restart service"),
        ("u", "update_service", "Update image"),
        ("l", "show_service_logs", "View logs"),
    ]

    class Updated(Message):
        def __init__(
            self,
            services: list[ComposeService],
            connected: bool,
        ) -> None:
            super().__init__()
            self.services = services
            self.connected = connected

    def __init__(
        self,
        docker_manager: DockerComposeManager | None,
        startup_error: str | None = None,
    ) -> None:
        super().__init__()
        self._docker = docker_manager
        self._startup_error = startup_error
        self._services: list[ComposeService] = []
        self._busy_services: set[str] = set()
        self._refresh_in_progress = False
        self._refresh_requested = False
        self._last_error: tuple[str, str] | None = None

    def compose(self) -> ComposeResult:
        yield Static("DOCKER SERVICES", classes="section-title")
        yield ServiceTable(id="service-table")
        yield Static("Select a service to see its details.", id="service-detail")
        with Horizontal(id="operation-feedback"):
            yield Static("Ready.", id="operation-status")
            yield LoadingIndicator(id="operation-progress")
        with Horizontal(id="service-actions"):
            yield Button("Start", id="start-service", variant="success")
            yield Button("Stop", id="stop-service", variant="warning")
            yield Button("Restart", id="restart-service")
            yield Button("Update Image", id="update-service")
            yield Button("View Logs", id="service-logs")
        yield Button("View error details", id="view-error", disabled=True)
        yield Static(
            "Select a service | S start | X stop | R restart | U update | L logs | Tab actions",
            id="service-help",
        )

    def on_mount(self) -> None:
        self._set_busy(False)
        if self._docker is None:
            self.query_one("#operation-status", Static).update(
                self._startup_error or "Deployment Compose configuration unavailable."
            )
            for button in self.query("#service-actions Button"):
                button.disabled = True
            if self._startup_error:
                self._last_error = ("Load deployment configuration", self._startup_error)
                error_button = self.query_one("#view-error", Button)
                error_button.disabled = False
                error_button.display = True
            self.post_message(self.Updated([], False))
            return
        self.refresh_services()
        self.set_interval(5.0, self.refresh_services)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "service-table":
            self._update_service_details()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions: dict[str, Callable[[], None]] = {
            "start-service": self.action_start_service,
            "stop-service": self.action_stop_service,
            "restart-service": self.action_restart_service,
            "update-service": self.action_update_service,
            "service-logs": self.action_show_service_logs,
        }
        action = actions.get(event.button.id or "")
        if action is not None:
            action()
        elif event.button.id == "view-error" and self._last_error is not None:
            operation, details = self._last_error
            self.app.push_screen(OperationErrorScreen(operation, details))

    @work(group="service-refresh")
    async def refresh_services(self) -> None:
        if not self.is_mounted:
            return
        if self._docker is None:
            return
        if self._refresh_in_progress:
            self._refresh_requested = True
            return

        self._refresh_in_progress = True
        try:
            available = await self._docker.get_services()
            running = await self._docker.get_status()
            if not self.is_mounted:
                return

            statuses = {service.name: service for service in running}
            self._services = [
                statuses.get(
                    name,
                    ComposeService(name, "Not created", "not created"),
                )
                for name in available
            ]
            self.query_one(ServiceTable).update_services(self._services)
            if not self._services:
                self.query_one("#service-detail", Static).update(
                    "No services are defined in the deployment Compose configuration."
                )
            else:
                self._update_service_details()
            self.post_message(self.Updated(self._services, True))
        except DockerComposeError as exc:
            if not self.is_mounted:
                return
            self.query_one(ServiceTable).mark_unavailable()
            self.query_one("#operation-status", Static).update(
                "Docker services are unavailable. Check Docker and the daemon."
            )
            self._record_error("Refresh services", str(exc))
            self.post_message(self.Updated(self._services, False))
        finally:
            self._refresh_in_progress = False
            if self._refresh_requested and self.is_mounted:
                self._refresh_requested = False
                self.refresh_services()

    def action_start_service(self) -> None:
        if self._docker is None:
            return
        self._run_service_action(self._docker.start, "Starting", "Started")

    def action_stop_service(self) -> None:
        if self._docker is None:
            return
        self._run_service_action(self._docker.stop, "Stopping", "Stopped")

    def action_restart_service(self) -> None:
        if self._docker is None:
            return
        service = self._selected_service()
        if service is None:
            return
        table = self.query_one(ServiceTable)
        if table.get_service_state(service) == "not created":
            self._set_operation_status(f"{service} has no container. Start it first.")
            return
        self._run_service_action(self._docker.restart, "Restarting", "Restarted", service)

    def action_update_service(self) -> None:
        if self._docker is None:
            return
        service = self._selected_service()
        if service is not None:
            self._update_service(service)

    def action_show_service_logs(self) -> None:
        if self._docker is None:
            return
        service = self._selected_service()
        if service is not None:
            self._show_service_logs(service)

    def _selected_service(self) -> str | None:
        service = self.query_one(ServiceTable).get_selected_service()
        if service is None:
            self._set_operation_status("Select a service before choosing an action.")
        return service

    def _update_service_details(self) -> None:
        service_name = self.query_one(ServiceTable).get_selected_service()
        if service_name is None:
            return
        service = next(
            (item for item in self._services if item.name == service_name),
            None,
        )
        if service is not None:
            self.query_one("#service-detail", Static).update(
                f"Service: {service.name}  |  State: {service.state}\n"
                f"Status: {service.status}  |  "
                "Image reference: docker/deploy/compose.yaml"
            )

    def _set_operation_status(self, message: str) -> None:
        self.query_one("#operation-status", Static).update(message)

    def _set_busy(self, busy: bool) -> None:
        self.query_one("#operation-progress", LoadingIndicator).display = busy
        for button in self.query("#service-actions Button"):
            button.disabled = busy

    def _record_error(self, operation: str, details: str) -> None:
        self._last_error = (operation, details)
        error_button = self.query_one("#view-error", Button)
        error_button.disabled = False
        error_button.display = True
        self.app.notify(
            f"{operation} failed. View error details for more information.",
            severity="error",
        )

    def _clear_error(self) -> None:
        self._last_error = None
        error_button = self.query_one("#view-error", Button)
        error_button.disabled = True
        error_button.display = False

    @work(group="service-operations", exclusive=False)
    async def _run_service_action(
        self,
        action: Callable[[str], Awaitable[None]],
        progress: str,
        success: str,
        service: str | None = None,
    ) -> None:
        if self._docker is None:
            return
        selected = service or self._selected_service()
        if selected is None:
            return
        if self._busy_services:
            self._set_operation_status(
                f"Wait for the current operation on {next(iter(self._busy_services))} to finish."
            )
            return

        self._busy_services.add(selected)
        self._clear_error()
        self._set_busy(True)
        self._set_operation_status(f"{progress} {selected}…")
        try:
            await action(selected)
            self._set_operation_status(f"{success}: {selected}")
        except DockerComposeError as exc:
            self._set_operation_status(f"Failed: {progress.lower()} {selected}.")
            self._record_error(f"{progress} {selected}", str(exc))
        finally:
            self._busy_services.remove(selected)
            self._set_busy(False)
            if self.is_mounted:
                self.refresh_services()

    @work(group="service-operations", exclusive=False)
    async def _update_service(self, service: str) -> None:
        if self._docker is None:
            return
        if self._busy_services:
            self._set_operation_status(
                f"Wait for the current operation on {next(iter(self._busy_services))} to finish."
            )
            return

        self._busy_services.add(service)
        self._clear_error()
        self._set_busy(True)
        self._set_operation_status(f"Pulling the configured image for {service}…")
        try:
            await self._docker.pull(service)
            status = await self._service_status(service)
            if status is None or status.state.lower() != "running":
                self._set_operation_status(
                    f"Image pulled for {service}. The service remains stopped."
                )
                return

            self._set_operation_status(
                f"Image pulled. Waiting for confirmation to update {service}."
            )
            confirmed = await self.app.push_screen_wait(UpdateConfirmation(service))
            if not confirmed:
                self._set_operation_status(
                    f"Image pulled for {service}; the running container was not changed."
                )
                return

            self._set_operation_status(f"Recreating {service} with the pulled image…")
            status = await self._service_status(service)
            if status is None or status.state.lower() != "running":
                self._set_operation_status(
                    f"{service} is no longer running. The container was not recreated."
                )
                return
            await self._docker.recreate(service)
            self._set_operation_status(f"Updated and restarted: {service}")
        except DockerComposeError as exc:
            self._set_operation_status(f"Failed to update {service}.")
            self._record_error(f"Update image for {service}", str(exc))
        finally:
            self._busy_services.remove(service)
            self._set_busy(False)
            if self.is_mounted:
                self.refresh_services()

    @work(group="service-logs", exclusive=False)
    async def _show_service_logs(self, service: str) -> None:
        if self._docker is None:
            return
        self._set_operation_status(f"Loading recent logs for {service}…")
        self.query_one("#operation-progress", LoadingIndicator).display = True
        try:
            logs = await self._docker.logs(service)
        except DockerComposeError as exc:
            self._set_operation_status(f"Could not load logs for {service}.")
            self._record_error(f"View logs for {service}", str(exc))
            self.query_one("#operation-progress", LoadingIndicator).display = False
            return

        self.query_one("#operation-progress", LoadingIndicator).display = False
        self._set_operation_status(f"Showing the latest logs for {service}.")
        self.app.push_screen(ServiceLogsScreen(service, logs))

    async def _service_status(self, service: str) -> ComposeService | None:
        if self._docker is None:
            return None
        return next(
            (item for item in await self._docker.get_status() if item.name == service),
            None,
        )
