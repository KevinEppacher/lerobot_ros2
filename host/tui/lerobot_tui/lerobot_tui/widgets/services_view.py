import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

from textual import work
from textual.app import ComposeResult, SuspendNotSupported
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, DataTable, LoadingIndicator, Static

from lerobot_tui.backends.docker import (
    ComposeService,
    DockerComposeError,
    DockerComposeManager,
    ToolExecutionResult,
    ToolMetadata,
)
from lerobot_tui.screens.operation_error import OperationErrorScreen
from lerobot_tui.screens.service_info import ServiceInfoScreen
from lerobot_tui.screens.service_logs import ServiceLogsScreen
from lerobot_tui.screens.tool_dialogs import (
    ToolConfigurationScreen,
    ToolExecutionConfirmation,
    ToolOutputScreen,
)
from lerobot_tui.screens.update_confirmation import UpdateConfirmation
from lerobot_tui.widgets.service_table import SERVICE_LOGO, ServiceTable


class ServicesView(Widget):
    BINDINGS = [
        ("s", "start_service", "Start service"),
        ("x", "stop_service", "Stop service"),
        ("r", "restart_service", "Restart service"),
        ("u", "update_service", "Update image"),
        ("l", "show_service_logs", "View logs"),
        ("f", "show_service_info", "Service info"),
        ("c", "configure_tool", "Configure tool"),
        ("t", "run_tool", "Run tool"),
        ("i", "run_interactive_tool", "Run interactive tool"),
        ("o", "show_tool_output", "View tool output"),
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
        self._active_category = "All"
        self._preferred_service: str | None = None
        self._tool_environment: dict[str, dict[str, str]] = {}
        self._tool_results: dict[str, ToolExecutionResult] = {}
        self._refresh_in_progress = False
        self._refresh_requested = False
        self._last_error: tuple[str, str] | None = None

    def compose(self) -> ComposeResult:
        yield Static(
            "\n".join(SERVICE_LOGO.splitlines()[5:]),
            id="services-logo",
            markup=False,
        )
        yield Static("DOCKER SERVICES", classes="section-title")
        with Horizontal(id="category-filters"):
            for category in (
                "All",
                "Bringup",
                "Infrastructure",
                "Motion",
                "Calibration",
                "Tools",
            ):
                yield Button(category, id=f"category-{category.lower()}")
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
            yield Button("Configure", id="configure-tool")
            yield Button("Run", id="run-tool", variant="success")
            yield Button("Run Interactive", id="run-interactive", variant="warning")
            yield Button("View Output", id="view-tool-output")
            yield Button("Info", id="service-info")
        yield Button("View error details", id="view-error", disabled=True)
        yield Static(
            "S/X/R/U/L service | C config | T run | I interactive | "
            "O output | F info | Tab actions",
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
            "service-info": self.action_show_service_info,
            "configure-tool": self.action_configure_tool,
            "run-tool": self.action_run_tool,
            "run-interactive": self.action_run_interactive_tool,
            "view-tool-output": self.action_show_tool_output,
        }
        action = actions.get(event.button.id or "")
        if action is not None:
            action()
        elif event.button.id and event.button.id.startswith("category-"):
            category = event.button.id.removeprefix("category-")
            self._set_category("All" if category == "all" else category.title())
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
        catalog: list[ComposeService] | None = None
        try:
            catalog = await self._docker.get_catalog()
            running = await self._docker.get_status()
            if not self.is_mounted:
                return

            statuses = {service.name: service for service in running}
            self._services = [
                ComposeService(
                    name=definition.name,
                    status=statuses.get(definition.name, definition).status,
                    state=statuses.get(definition.name, definition).state,
                    category=definition.category,
                    execution_type=definition.execution_type,
                    source_compose=definition.source_compose,
                    image=definition.image,
                    command=definition.command,
                    environment_variables=definition.environment_variables,
                    dockerfile=definition.dockerfile,
                    documentation=definition.documentation,
                )
                for definition in catalog
            ]
            self._update_visible_services()
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
            if catalog is not None:
                self._services = [
                    ComposeService(
                        name=service.name,
                        status="Unavailable",
                        state="unavailable",
                        category=service.category,
                        execution_type=service.execution_type,
                        source_compose=service.source_compose,
                        image=service.image,
                        command=service.command,
                        environment_variables=service.environment_variables,
                        dockerfile=service.dockerfile,
                        documentation=service.documentation,
                    )
                    for service in catalog
                ]
                self._update_visible_services()
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
        service = self._selected_persistent_service()
        if service is not None:
            self._run_service_action(self._docker.start, "Starting", "Started", service)

    def action_stop_service(self) -> None:
        if self._docker is None:
            return
        service = self._selected_persistent_service()
        if service is not None:
            self._run_service_action(self._docker.stop, "Stopping", "Stopped", service)

    def action_restart_service(self) -> None:
        if self._docker is None:
            return
        service = self._selected_persistent_service()
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
        service = self._selected_persistent_service()
        if service is not None:
            self._update_service(service)

    def action_show_service_logs(self) -> None:
        if self._docker is None:
            return
        service = self._selected_persistent_service()
        if service is not None:
            self._show_service_logs(service)

    def action_show_service_info(self) -> None:
        service_name = self._selected_service()
        service = next(
            (item for item in self._services if item.name == service_name),
            None,
        )
        if service is not None:
            self.app.push_screen(ServiceInfoScreen(service))

    def action_configure_tool(self) -> None:
        service = self._selected_service()
        metadata = self._tool_definition(service)
        if service is not None and metadata is not None and metadata.environment_variables:
            self._configure_tool(service)

    def action_run_tool(self) -> None:
        service = self._selected_service()
        definition = self._tool_definition(service) if service is not None else None
        if definition is not None and definition.execution_type == "one-shot":
            self._run_one_shot_tool(service)

    def action_run_interactive_tool(self) -> None:
        service = self._selected_service()
        definition = self._tool_definition(service) if service is not None else None
        if definition is not None and definition.execution_type == "interactive":
            self._run_interactive_tool(service)

    def action_show_tool_output(self) -> None:
        service = self._selected_service()
        if service is not None:
            result = self._tool_results.get(service)
            if result is not None:
                self.app.push_screen(
                    ToolOutputScreen(
                        service,
                        result.exit_code,
                        result.stdout,
                        result.stderr,
                    )
                )

    def _set_category(self, category: str) -> None:
        self._active_category = category
        self._update_visible_services()

    def _update_visible_services(self) -> None:
        if not self.is_mounted:
            return
        visible = [
            service
            for service in self._services
            if self._active_category == "All" or service.category == self._active_category
        ]
        self.query_one(ServiceTable).update_services(
            visible,
            preferred_service=self._preferred_service,
        )
        self._update_service_details()

    def _selected_service(self) -> str | None:
        table = self.query_one(ServiceTable)
        service = table.get_selected_service()
        if service is None:
            self._set_operation_status("Select a service before choosing an action.")
        else:
            self._preferred_service = service
        return service

    def _selected_persistent_service(self) -> str | None:
        service = self._selected_service()
        definition = next(
            (item for item in self._services if item.name == service),
            None,
        )
        if service is not None and (definition is None or definition.execution_type != "service"):
            self._set_operation_status(
                "Lifecycle actions are only available for persistent services."
            )
            return None
        return service

    def _update_service_details(self) -> None:
        table = self.query_one(ServiceTable)
        service_name = table.get_selected_service()
        if service_name is None:
            for button in self.query("#service-actions Button"):
                button.display = False
            return
        self._preferred_service = service_name
        service = next(
            (item for item in self._services if item.name == service_name),
            None,
        )
        if service is not None:
            self.query_one("#service-detail", Static).update(
                f"Service: {service.name} | Category: {service.category} | "
                f"Type: {service.execution_type}\n"
                f"State: {service.state} | Status: {service.status}"
            )
            persistent = service.execution_type == "service"
            one_shot = service.execution_type == "one-shot"
            interactive = service.execution_type == "interactive"
            metadata = self._tool_definition(service.name)
            visibility = {
                "start-service": persistent,
                "stop-service": persistent,
                "restart-service": persistent,
                "update-service": persistent,
                "service-logs": persistent,
                "configure-tool": one_shot or interactive,
                "run-tool": one_shot,
                "run-interactive": interactive,
                "view-tool-output": one_shot,
                "service-info": True,
            }
            for button_id, visible in visibility.items():
                button = self.query_one(f"#{button_id}", Button)
                button.display = visible
                unavailable = (
                    button_id == "configure-tool"
                    and (metadata is None or not metadata.environment_variables)
                ) or (button_id == "view-tool-output" and service.name not in self._tool_results)
                button.disabled = bool(self._busy_services) or unavailable

    def _tool_definition(self, service: str | None) -> ToolMetadata | None:
        if self._docker is None or service is None:
            return None
        definition = next(
            (item for item in self._services if item.name == service),
            None,
        )
        if definition is None or definition.execution_type == "service":
            return None
        return self._docker.metadata_for(service)

    def _tool_values(self, service: str, variables: tuple[str, ...]) -> dict[str, str]:
        if self._docker is None:
            return {}
        saved = self._tool_environment.get(service, {})
        values: dict[str, str] = {}
        for variable in variables:
            value = (
                saved[variable] if variable in saved else self._docker.environment_value(variable)
            )
            if not value and variable.endswith("_DOF"):
                value = "5"
            elif not value and variable == "TORQUE_MODE":
                value = "off"
            elif not value and variable.endswith("_CALIBRATION_FILE"):
                dof_variable = variable.removesuffix("_CALIBRATION_FILE") + "_DOF"
                dof = values.get(dof_variable, "5")
                value = self._docker.default_calibration_file(variable, dof)
            values[variable] = value
        return values

    @work(group="tool-configuration")
    async def _configure_tool(self, service: str) -> None:
        metadata = self._tool_definition(service)
        if metadata is None:
            return
        values = await self.app.push_screen_wait(
            ToolConfigurationScreen(
                service,
                metadata,
                self._tool_values(service, metadata.environment_variables),
                calibration_files=self._docker.calibration_files(),
                calibration_directories=self._docker.calibration_directories(),
                calibration_path_resolver=self._docker.resolve_calibration_path,
            )
        )
        if values is None:
            self._set_operation_status(f"Configuration cancelled for {service}.")
            return
        calibration_host_path: Path | None = None
        try:
            for variable in metadata.environment_variables:
                if variable.endswith("_CALIBRATION_FILE"):
                    values[variable], calibration_host_path = self._docker.save_calibration_file(
                        variable, values[variable]
                    )
        except (OSError, ValueError, DockerComposeError) as exc:
            self._set_operation_status(f"Could not save calibration configuration: {exc}")
            self._record_error(f"Configure {service}", str(exc))
            return
        self._tool_environment[service] = values
        status = f"Configuration saved for {service}."
        if calibration_host_path is not None:
            status += f" Output: {calibration_host_path}"
        self._set_operation_status(status)

    def _validate_tool_environment(
        self,
        service: str,
        metadata: ToolMetadata,
    ) -> dict[str, str] | None:
        values = self._tool_values(service, metadata.environment_variables)
        for variable in metadata.environment_variables:
            value = values.get(variable, "").strip()
            if variable.endswith("_PORT") and not value:
                self._set_operation_status(f"Configure {variable} before running {service}.")
                return None
            if variable == metadata.hardware_variable and value:
                try:
                    device_exists = Path(value).exists()
                except (OSError, ValueError) as exc:
                    self._set_operation_status(f"Could not validate device path: {exc}")
                    return None
                if not device_exists:
                    self._set_operation_status(f"Device path does not exist: {value}")
                    return None
            if value:
                if variable.endswith("_CALIBRATION_FILE"):
                    try:
                        container_path, _ = self._docker.prepare_calibration_output(value)
                    except (OSError, ValueError) as exc:
                        self._set_operation_status(f"Invalid calibration output path: {exc}")
                        return None
                    value = container_path
                values[variable] = value
            else:
                values.pop(variable, None)
        return values

    async def _confirm_tool_execution(
        self,
        service: str,
        metadata: ToolMetadata,
        interactive: bool,
    ) -> bool:
        warnings: list[str] = []
        overwrite_path: str | None = None
        if metadata.hardware_access:
            device = (
                self._tool_values(service, metadata.environment_variables).get(
                    metadata.hardware_variable, ""
                )
                if metadata.hardware_variable
                else ""
            )
            if device and self._docker is not None:
                users = await self._docker.active_services_using_device(device)
                if users:
                    warnings.append(
                        f"{device} is also mapped by running service(s): "
                        f"{', '.join(users)}. Stop them before proceeding if they use "
                        "the same hardware."
                    )
            elif not device:
                warnings.append(
                    "This tool accesses host hardware. Ensure no other process or service "
                    "is using the device."
                )
        if metadata.may_overwrite_calibration:
            calibration_variable = next(
                (
                    variable
                    for variable in metadata.environment_variables
                    if variable.endswith("_CALIBRATION_FILE")
                ),
                None,
            )
            if calibration_variable is not None and self._docker is not None:
                try:
                    _, host_path = self._docker.prepare_calibration_output(
                        self._tool_values(service, metadata.environment_variables)[
                            calibration_variable
                        ]
                    )
                    if host_path.exists():
                        overwrite_path = str(host_path)
                except (OSError, ValueError) as exc:
                    self._set_operation_status(f"Invalid calibration output path: {exc}")
                    return False
        return bool(
            await self.app.push_screen_wait(
                ToolExecutionConfirmation(
                    service,
                    warnings,
                    interactive,
                    metadata.may_overwrite_calibration,
                    overwrite_path,
                )
            )
        )

    @work(group="service-operations", exclusive=False)
    async def _run_one_shot_tool(self, service: str) -> None:
        if self._docker is None:
            return
        metadata = self._tool_definition(service)
        if metadata is None or metadata.execution_type != "one-shot":
            return
        if self._busy_services:
            self._set_operation_status(
                f"Wait for the current operation on {next(iter(self._busy_services))} to finish."
            )
            return
        environment = self._validate_tool_environment(service, metadata)
        if environment is None:
            return
        self._busy_services.add(service)
        self._clear_error()
        self._set_busy(True)
        try:
            if not await self._confirm_tool_execution(service, metadata, False):
                self._set_operation_status(f"Run cancelled for {service}.")
                return
            self._set_operation_status(f"Running {service}…")
            result = await self._docker.run_tool(service, environment)
            self._tool_results[service] = result
            self._update_service_details()
            if result.exit_code == 0:
                self._set_operation_status(f"Completed: {service}")
            else:
                self._set_operation_status(f"{service} failed with exit code {result.exit_code}.")
                details = result.stderr or result.stdout or "The tool returned no output."
                self._record_error(f"Run {service}", details)
            self.app.push_screen(
                ToolOutputScreen(
                    service,
                    result.exit_code,
                    result.stdout,
                    result.stderr,
                )
            )
        except DockerComposeError as exc:
            self._set_operation_status(f"Failed to run {service}.")
            self._record_error(f"Run {service}", str(exc))
        finally:
            self._busy_services.remove(service)
            self._set_busy(False)

    @work(group="service-operations", exclusive=False)
    async def _run_interactive_tool(self, service: str) -> None:
        if self._docker is None:
            return
        metadata = self._tool_definition(service)
        if metadata is None or metadata.execution_type != "interactive":
            return
        if self._busy_services:
            self._set_operation_status(
                f"Wait for the current operation on {next(iter(self._busy_services))} to finish."
            )
            return
        if not all(
            stream is not None and stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)
        ):
            self._set_operation_status(
                "Interactive tools require a real terminal; run this action from a TTY."
            )
            return
        environment = self._validate_tool_environment(service, metadata)
        if environment is None:
            return
        self._busy_services.add(service)
        self._clear_error()
        self._set_busy(True)
        try:
            if not await self._confirm_tool_execution(service, metadata, True):
                self._set_operation_status(f"Run cancelled for {service}.")
                return
            self._set_operation_status(f"Running interactive tool {service}…")
            operation_error: BaseException | None = None
            exit_code: int | None = None
            try:
                with self.app.suspend():
                    try:
                        # The suspended Textual driver must not receive redraws while it is closed.
                        exit_code = self._docker.run_interactive_tool(service, environment)
                    except BaseException as exc:
                        operation_error = exc
            except SuspendNotSupported as exc:
                self._set_operation_status(
                    "This terminal cannot be suspended for interactive tools."
                )
                self._record_error(f"Run {service}", str(exc))
                return

            if isinstance(operation_error, asyncio.CancelledError):
                self._set_operation_status(f"Cancelled: {service}")
                raise operation_error
            if isinstance(operation_error, KeyboardInterrupt):
                self._set_operation_status(f"Cancelled: {service}")
                return
            if operation_error is not None:
                if not isinstance(operation_error, Exception):
                    raise operation_error
                self._set_operation_status(f"Failed to run {service}.")
                self._record_error(f"Run {service}", str(operation_error))
                return
            if exit_code is None:
                self._set_operation_status(f"Cancelled: {service}")
                return

            self._tool_results[service] = ToolExecutionResult(exit_code, "", "")
            self._update_service_details()
            if exit_code == 0:
                self._set_operation_status(f"Completed: {service} (exit code 0)")
            else:
                self._set_operation_status(f"{service} failed with exit code {exit_code}.")
                self._record_error(
                    f"Run {service}",
                    f"The interactive process exited with status {exit_code}.",
                )
        except (DockerComposeError, OSError) as exc:
            self._set_operation_status(f"Failed to run {service}.")
            self._record_error(f"Run {service}", str(exc))
        finally:
            self._busy_services.discard(service)
            if self.is_mounted:
                self._set_busy(False)

    def _set_operation_status(self, message: str) -> None:
        self.query_one("#operation-status", Static).update(message)

    def _set_busy(self, busy: bool) -> None:
        self.query_one("#operation-progress", LoadingIndicator).display = busy
        for button in self.query("#service-actions Button"):
            button.disabled = busy
        if not busy:
            self._update_service_details()

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
