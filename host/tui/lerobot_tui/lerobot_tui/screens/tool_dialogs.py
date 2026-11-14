from collections.abc import Callable
from pathlib import Path, PurePosixPath

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, RichLog, Select, Static

from lerobot_tui.backends.docker import ToolMetadata


class ToolConfigurationScreen(ModalScreen[dict[str, str] | None]):
    def __init__(
        self,
        service: str,
        metadata: ToolMetadata,
        values: dict[str, str],
        calibration_files: list[tuple[str, str]] | None = None,
        calibration_directories: list[tuple[str, str]] | None = None,
        calibration_path_resolver: Callable[[str], Path] | None = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._variables = metadata.environment_variables
        self._values = values
        self._calibration_files = calibration_files or []
        self._calibration_directories = calibration_directories or []
        self._calibration_path_resolver = calibration_path_resolver

    def compose(self) -> ComposeResult:
        with Vertical(id="tool-configuration"):
            yield Static(f"Configure {self._service}", classes="section-title")
            with VerticalScroll(id="tool-config-fields"):
                for variable in self._variables:
                    yield Static(variable.replace("_", " ").title())
                    if variable.endswith("_DOF"):
                        value = self._values.get(variable, "")
                        yield Select(
                            [("5 DOF", "5"), ("6 DOF", "6")],
                            value=value if value in {"5", "6"} else "5",
                            allow_blank=False,
                            id=f"config-{variable}",
                        )
                    elif variable == "TORQUE_MODE":
                        value = self._values.get(variable, "").lower()
                        yield Select(
                            [("On", "on"), ("Off", "off")],
                            value=value if value in {"on", "off"} else "off",
                            allow_blank=False,
                            id=f"config-{variable}",
                        )
                    elif variable.endswith("_PORT"):
                        yield Input(
                            self._values.get(variable, ""),
                            placeholder="Select or enter a serial device path",
                            id=f"config-{variable}",
                        )
                        yield Select(
                            self._serial_devices(),
                            prompt="Detected serial devices",
                            id=f"detected-{variable}",
                        )
                    elif variable.endswith("_CALIBRATION_FILE"):
                        value = self._values.get(variable, "")
                        yield Input(
                            value,
                            placeholder="/config/calibration/5dof/my_robot.yaml",
                            id=f"config-{variable}",
                        )
                        yield Select(
                            self._calibration_directories,
                            prompt="Select calibration directory",
                            id=f"calibration-directory-{variable}",
                        )
                        yield Select(
                            self._calibration_files,
                            prompt="Select existing calibration file",
                            id=f"calibration-file-{variable}",
                        )
                        yield Static(
                            self._calibration_preview(value),
                            id=f"calibration-host-{variable}",
                        )
            yield Static("", id="tool-config-error")
            yield Button("Save configuration", id="save-tool-config", variant="primary")
            yield Button("Cancel", id="cancel-tool-config")

    @staticmethod
    def _serial_devices() -> list[tuple[str, str]]:
        candidates = sorted(Path("/dev/serial/by-id").glob("*"))
        options = [(str(path), str(path)) for path in candidates]
        if not options:
            options.append(("No /dev/serial/by-id devices detected", ""))
        return options

    def on_select_changed(self, event: Select.Changed) -> None:
        if not event.select.id:
            return
        if event.select.id.startswith("detected-"):
            variable = event.select.id.removeprefix("detected-")
            input_widget = self.query_one(f"#config-{variable}", Input)
            input_widget.value = str(event.value) if event.value else ""
            return
        if event.select.id.startswith("calibration-file-"):
            variable = event.select.id.removeprefix("calibration-file-")
            input_widget = self.query_one(f"#config-{variable}", Input)
            input_widget.value = str(event.value) if event.value else ""
            return
        if event.select.id.startswith("calibration-directory-"):
            variable = event.select.id.removeprefix("calibration-directory-")
            input_widget = self.query_one(f"#config-{variable}", Input)
            filename = PurePosixPath(input_widget.value).name or (
                "leader_example_calibration.yaml"
                if variable.startswith("LEADER_")
                else "follower_example_calibration.yaml"
            )
            input_widget.value = str(PurePosixPath(str(event.value)) / filename)

    def on_input_changed(self, event: Input.Changed) -> None:
        if not event.input.id or not event.input.id.startswith("config-"):
            return
        variable = event.input.id.removeprefix("config-")
        if variable.endswith("_CALIBRATION_FILE"):
            self.query_one(f"#calibration-host-{variable}", Static).update(
                self._calibration_preview(event.value)
            )

    def _calibration_preview(self, value: str) -> str:
        if self._calibration_path_resolver is None:
            return "Host path: unavailable"
        try:
            return f"Host path: {self._calibration_path_resolver(value)}"
        except (OSError, ValueError) as exc:
            return f"Host path: invalid ({exc})"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-tool-config":
            self.dismiss(None)
        elif event.button.id == "save-tool-config":
            values: dict[str, str] = {}
            for variable in self._variables:
                widget_id = f"#config-{variable}"
                widget = self.query_one(widget_id)
                value = widget.value if isinstance(widget, Select) else widget.value
                if variable.endswith("_CALIBRATION_FILE") and self._calibration_path_resolver:
                    try:
                        self._calibration_path_resolver(str(value).strip())
                    except (OSError, ValueError) as exc:
                        self.query_one("#tool-config-error", Static).update(str(exc))
                        self.query_one("#tool-config-error", Static).display = True
                        return
                values[variable] = str(value).strip()
            self.dismiss(values)


class ToolExecutionConfirmation(ModalScreen[bool]):
    def __init__(
        self,
        service: str,
        warnings: list[str],
        interactive: bool,
        may_overwrite_calibration: bool = False,
        calibration_overwrite_path: str | None = None,
    ) -> None:
        super().__init__()
        self._service = service
        self._warnings = warnings
        self._interactive = interactive
        self._may_overwrite_calibration = may_overwrite_calibration
        self._calibration_overwrite_path = calibration_overwrite_path

    def compose(self) -> ComposeResult:
        with Vertical(id="tool-confirmation"):
            yield Static(f"Run {self._service}?", classes="section-title")
            if self._interactive:
                yield Static(
                    "The TUI will temporarily release this terminal. "
                    "After the process exits, review its output and press Enter to return."
                )
            for warning in self._warnings:
                yield Static(warning, classes="tool-warning")
            if self._calibration_overwrite_path is not None:
                yield Static(
                    f"This calibration will overwrite the existing file:\n"
                    f"{self._calibration_overwrite_path}",
                    classes="tool-warning",
                )
            elif self._may_overwrite_calibration:
                yield Static(
                    "Calibration output is saved to the configured path.",
                    classes="tool-warning",
                )
            yield Button("Continue", id="confirm-tool", variant="warning")
            yield Button("Cancel", id="cancel-tool")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-tool":
            self.dismiss(True)
        elif event.button.id == "cancel-tool":
            self.dismiss(False)


class ToolOutputScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    def __init__(
        self,
        service: str,
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> None:
        super().__init__()
        self.service = service
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

    def compose(self) -> ComposeResult:
        result = "Completed" if self.exit_code == 0 else "Failed"
        yield Static(f"TOOL OUTPUT: {self.service}", classes="section-title")
        yield Static(f"{result} | Exit code: {self.exit_code}", id="tool-result")
        yield RichLog(id="tool-output", wrap=False, markup=False)
        yield Button("Close", id="close-tool-output")
        yield Footer()

    def on_mount(self) -> None:
        output = self.query_one("#tool-output", RichLog)
        output.write(self.stdout or "(No standard output)")
        if self.stderr:
            output.write("\n--- stderr ---\n")
            output.write(self.stderr)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-tool-output":
            self.dismiss()
