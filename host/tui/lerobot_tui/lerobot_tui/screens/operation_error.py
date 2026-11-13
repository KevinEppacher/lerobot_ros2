from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Static


class OperationErrorScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    def __init__(self, operation: str, details: str) -> None:
        super().__init__()
        self._operation = operation
        self._details = details

    def compose(self) -> ComposeResult:
        yield Static(f"Operation failed: {self._operation}", classes="section-title")
        yield Static(self._details, id="operation-error-details", markup=False)
        yield Button("Close", id="close-error")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-error":
            self.dismiss()
