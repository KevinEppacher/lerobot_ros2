from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static

from lerobot_tui.backends.docker import ComposeService


class ServiceInfoScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    def __init__(self, service: ComposeService) -> None:
        super().__init__()
        self._service = service

    def compose(self) -> ComposeResult:
        service = self._service
        execution_type = {
            "service": "Persistent service",
            "one-shot": "One-shot tool",
            "interactive": "Interactive tool",
        }.get(service.execution_type, service.execution_type)
        details = (
            f"SERVICE: {service.name}\n\n"
            f"Category:\n{service.category}\n\n"
            f"Execution Type:\n{execution_type}\n\n"
            f"Compose File:\n{service.source_compose}\n\n"
            f"Image:\n{service.image}\n\n"
            f"Command:\n{service.command}\n\n"
            f"Environment Variables:\n"
            f"{', '.join(service.environment_variables) or 'None specified'}\n\n"
            f"Dockerfile:\n{service.dockerfile}\n\n"
            f"Usage / Documentation:\n{service.documentation}"
        )
        with Vertical(id="service-information"):
            yield Static("SERVICE INFORMATION", classes="section-title")
            with VerticalScroll(id="service-information-content"):
                yield Static(details, markup=False)
            yield Button("Close", id="close-service-info")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-service-info":
            self.dismiss()
