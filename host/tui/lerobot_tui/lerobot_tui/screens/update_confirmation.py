from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class UpdateConfirmation(ModalScreen[bool]):
    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def compose(self) -> ComposeResult:
        with Vertical(id="update-confirmation"):
            yield Static(
                f"Updating {self._service} will interrupt its running container. "
                "Recreate it with the newly pulled image?"
            )
            yield Button("Recreate service", id="confirm-update", variant="error")
            yield Button("Cancel", id="cancel-update")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-update":
            self.dismiss(True)
        elif event.button.id == "cancel-update":
            self.dismiss(False)
