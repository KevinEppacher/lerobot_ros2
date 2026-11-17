from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    LoadingIndicator,
    Static,
    Tab,
    Tabs,
)

from lerobot_tui.backends.docker import (
    ALL_SERVICES,
    INTERACTIVE_RUN_ARGS,
    INTERACTIVE_SERVICES,
    ONESHOT_SERVICES,
    RUN_ARGS,
    SERVICES,
    DockerCompose,
)
from lerobot_tui.screens.operation_error import OperationErrorScreen
from lerobot_tui.screens.service_logs import ServiceLogsScreen
from lerobot_tui.widgets.service_table import SERVICE_LOGO, ServiceTable


class ServicesView(Widget):
    CATEGORY_TABS = ("All", *SERVICES.keys())

    BINDINGS = [
        ("s", "start_service", "Start"),
        ("x", "stop_service", "Stop"),
        ("r", "restart_service", "Restart"),
        ("l", "show_service_logs", "Logs"),
        ("e", "run_service", "Run"),
        Binding(
            "left",
            "previous_category",
            "Previous Category",
            show=False,
            priority=True,
        ),
        Binding(
            "right",
            "next_category",
            "Next Category",
            show=False,
            priority=True,
        ),
    ]

    COMMANDS = {
        "start": ("up", "-d"),
        "stop": ("stop",),
        "restart": ("restart",),
        "logs": ("logs", "--tail", "100"),
        "run": RUN_ARGS,
        "interactive": INTERACTIVE_RUN_ARGS,
    }

    class Updated(Message):
        def __init__(self, services: dict[str, str], connected: bool) -> None:
            super().__init__()
            self.services = services
            self.connected = connected

    def __init__(
        self,
        docker: DockerCompose | None,
        startup_error: str | None = None,
    ) -> None:
        super().__init__()
        self._docker = docker
        self._startup_error = startup_error
        self._services = {service: "not created" for service in ALL_SERVICES}
        self._busy = False
        self._refreshing = False
        self._selected_action = "start"
        self._last_error: tuple[str, str] | None = None
        self._category = "All"

    def compose(self) -> ComposeResult:
        yield Static(
            "\n".join(SERVICE_LOGO.splitlines()[5:]),
            id="services-logo",
            markup=False,
        )

        yield Static("DOCKER SERVICES", classes="section-title")

        yield Tabs(
            Tab("All", id="tab-all"),
            *(Tab(category, id=f"tab-{category.lower()}") for category in SERVICES),
            id="service-tabs",
        )

        yield ServiceTable(id="service-table")

        yield Static("", id="service-detail")
        yield Static("", id="service-command")

        with Horizontal(id="operation-feedback"):
            yield Static("Ready.", id="operation-status")
            yield LoadingIndicator(id="operation-progress")

        with Horizontal(id="service-actions"):
            yield Button("Start", id="start-service", variant="success")
            yield Button("Stop", id="stop-service", variant="warning")
            yield Button("Restart", id="restart-service")
            yield Button("View Logs", id="service-logs")
            yield Button("Run", id="run-service", variant="success")
            yield Button("Run Interactive", id="run-interactive", variant="primary")

        yield Button("View error details", id="view-error", disabled=True)

        yield Static(
            "S Start | X Stop | R Restart | L Logs | E Run",
            id="service-help",
        )

    def on_mount(self) -> None:
        self.query_one(ServiceTable).show_category(
            self._category,
            self._services,
        )

        if self._docker is None:
            self._set_status(self._startup_error or "Docker configuration unavailable.")
            self._set_busy(True)
            self.post_message(self.Updated(self._services.copy(), False))
            return

        self._update_details()
        self.refresh_services()
        self._update_actions()
        self.set_interval(5.0, self.refresh_services)

        self.call_after_refresh(self.query_one(ServiceTable).focus)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "service-table":
            self._update_details()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "start-service": self.action_start_service,
            "stop-service": self.action_stop_service,
            "restart-service": self.action_restart_service,
            "service-logs": self.action_show_service_logs,
            "run-service": self.action_run_service,
            "run-interactive": self.action_run_interactive,
        }

        action = actions.get(event.button.id)
        if action is not None:
            action()
        elif event.button.id == "view-error" and self._last_error:
            operation, details = self._last_error
            self.app.push_screen(OperationErrorScreen(operation, details))

    def _selected_service(self) -> str | None:
        return self.query_one(ServiceTable).get_selected_service()

    def _set_status(self, message: str) -> None:
        self.query_one("#operation-status", Static).update(message)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.query_one("#operation-progress", LoadingIndicator).display = busy

        for button in self.query("#service-actions Button"):
            button.disabled = busy

    def _show_error(self, operation: str, details: str) -> None:
        self._last_error = (operation, details)
        self.query_one("#view-error", Button).display = True
        self.query_one("#view-error", Button).disabled = False
        self.app.notify(f"{operation} failed.", severity="error")

    def _update_details(self) -> None:
        service = self._selected_service()
        if service is None:
            return

        state = self._services.get(service, "not created")
        service_type = self._service_type(service)

        self.query_one("#service-detail", Static).update(
            f"Service: {service} | Type: {service_type} | State: {state}"
        )

        if self._docker is not None:
            action = self._selected_action

            if service_type == "oneshot":
                action = "run"
            elif service_type == "interactive":
                action = "interactive"
            elif action not in {"start", "stop", "restart", "logs"}:
                action = "start"

            command = self.COMMANDS[action]

            self.query_one("#service-command", Static).update(
                f"Path:    {self._docker.directory}\n"
                f"Command: {self._docker.preview(*command, service)}"
            )

        self._update_actions()

    @work(group="service-refresh", exclusive=True)
    async def refresh_services(self) -> None:
        if self._docker is None or self._refreshing or self._busy:
            return

        self._refreshing = True

        try:
            services = await self._docker.status()
            self._services = services
            self.query_one(ServiceTable).update_services(services)
            self._update_details()
            self.post_message(self.Updated(services.copy(), True))

        except Exception:
            unavailable = {service: "unavailable" for service in ALL_SERVICES}
            self._services = unavailable
            self.query_one(ServiceTable).update_services(unavailable)
            self._update_details()
            self._set_status("Docker is unavailable.")
            self.post_message(self.Updated(unavailable.copy(), False))

        finally:
            self._refreshing = False

    def action_start_service(self) -> None:
        self._run_action("start")

    def action_stop_service(self) -> None:
        self._run_action("stop")

    def action_restart_service(self) -> None:
        self._run_action("restart")

    def action_show_service_logs(self) -> None:
        self._run_action("logs")

    @work(group="service-operations", exclusive=True)
    async def _run_action(self, action: str) -> None:
        if self._docker is None or self._busy:
            return

        service = self._selected_service()
        if service is None:
            return

        service_type = self._service_type(service)

        allowed_actions = {
            "persistent": {"start", "stop", "restart", "logs"},
            "oneshot": {"run"},
            "interactive": set(),
        }

        if action not in allowed_actions[service_type]:
            return

        self._selected_action = action
        self._update_details()

        command = self.COMMANDS[action]

        self._set_busy(True)
        self._set_status(f"Executing: {self._docker.preview(*command, service)}")

        try:
            if action == "logs":
                output = await self._docker.logs(service)
                self.app.push_screen(ServiceLogsScreen(service, output))

            elif action == "run":
                output = await self._docker.run(service)
                self.app.push_screen(ServiceLogsScreen(service, output))

            else:
                await getattr(self._docker, action)(service)
                self._set_status(f"{action.capitalize()} completed: {service}")

        except Exception as exc:
            self._set_status(f"{action.capitalize()} failed: {service}")
            self._show_error(action.capitalize(), str(exc))

        finally:
            self._set_busy(False)
            self.refresh_services()

    @staticmethod
    def _service_type(service: str) -> str:
        if service in INTERACTIVE_SERVICES:
            return "interactive"

        if service in ONESHOT_SERVICES:
            return "oneshot"

        return "persistent"

    def _update_actions(self) -> None:
        service = self._selected_service()
        if service is None:
            return

        service_type = self._service_type(service)

        persistent = service_type == "persistent"
        oneshot = service_type == "oneshot"
        interactive = service_type == "interactive"

        self.query_one("#start-service", Button).display = persistent
        self.query_one("#stop-service", Button).display = persistent
        self.query_one("#restart-service", Button).display = persistent
        self.query_one("#service-logs", Button).display = persistent

        self.query_one("#run-service", Button).display = oneshot
        self.query_one("#run-interactive", Button).display = interactive

    def action_run_service(self) -> None:
        self._run_action("run")

    def action_run_interactive(self) -> None:
        if self._docker is None or self._busy:
            return

        service = self._selected_service()
        if service is None or service not in INTERACTIVE_SERVICES:
            return

        self._selected_action = "interactive"
        self._update_details()
        self._set_busy(True)

        try:
            with self.app.suspend():
                exit_code = self._docker.run_interactive(service)

            if exit_code == 0:
                self._set_status(f"Completed: {service}")
            else:
                self._set_status(f"Failed: {service} (exit code {exit_code})")
                self._show_error(
                    "Interactive",
                    f"Service '{service}' exited with code {exit_code}.",
                )

        except Exception as exc:
            self._set_status(f"Failed: {service}")
            self._show_error("Interactive", str(exc))

        finally:
            self._set_busy(False)
            self.refresh_services()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        tab_id = event.tab.id

        self._category = next(
            (category for category in SERVICES if tab_id == f"tab-{category.lower()}"),
            "All",
        )

        self.query_one(ServiceTable).show_category(
            self._category,
            self._services,
        )

        self._update_details()
        self._update_actions()

    def action_next_category(self) -> None:
        index = self.CATEGORY_TABS.index(self._category)
        next_index = (index + 1) % len(self.CATEGORY_TABS)
        self._switch_category(self.CATEGORY_TABS[next_index])

    def action_previous_category(self) -> None:
        index = self.CATEGORY_TABS.index(self._category)
        previous_index = (index - 1) % len(self.CATEGORY_TABS)
        self._switch_category(self.CATEGORY_TABS[previous_index])

    def _switch_category(self, category: str) -> None:
        tabs = self.query_one("#service-tabs", Tabs)
        tabs.active = f"tab-{category.lower()}"

        self.query_one(ServiceTable).focus()
