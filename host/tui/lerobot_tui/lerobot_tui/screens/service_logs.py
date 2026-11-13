from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Footer, RichLog, Static


class ServiceLogsScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    def __init__(self, service: str, logs: str) -> None:
        super().__init__()
        self._service = service
        self._logs = logs

    def compose(self) -> ComposeResult:
        yield Static(f"Logs: {self._service}", classes="section-title")
        yield RichLog(id="service-logs", wrap=False, markup=False)
        yield Footer()

    def on_mount(self) -> None:
        log_view = self.query_one("#service-logs", RichLog)
        log_view.write(self._logs or "(No logs available)")
