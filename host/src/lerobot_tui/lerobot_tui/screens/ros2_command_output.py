from collections import deque
from contextlib import suppress

from rich.text import Text
from textual import events, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, RichLog, Static
from textual.worker import WorkerCancelled

from lerobot_tui.backends.ros2_cli import Ros2CliBackend, Ros2CliError
from lerobot_tui.models import RosGraphCategory


class Ros2CommandOutputScreen(ModalScreen[None]):
    BINDINGS = [
        ("escape,q", "close", "Close"),
        ("p", "pause_output", "Pause/Resume"),
        ("c", "clear_output", "Clear"),
    ]

    def __init__(
        self,
        backend: Ros2CliBackend,
        category: RosGraphCategory,
        operation: str,
        target: str,
        message_type: str = "",
    ) -> None:
        super().__init__()
        self._backend = backend
        self._category = category
        self._operation = operation
        self._target = target
        self._message_type = message_type
        self._streaming = operation in {"echo", "hz"}
        self._paused = False
        self._received = False
        self._close_requested = False
        self._pending: deque[tuple[str, bool]] = deque(maxlen=256)

    def compose(self) -> ComposeResult:
        title = (
            "ROS 2 Interface"
            if self._operation == "interface"
            else (f"ROS 2 {self._category.value.title()} {self._operation.title()}")
        )
        yield Static(title, classes="section-title")
        yield Static(
            self._backend.preview(
                self._category, self._operation, self._target, self._message_type
            ),
            id="ros-command",
            markup=False,
        )
        yield RichLog(
            id="ros-output",
            max_lines=1000 if self._streaming else None,
            auto_scroll=False,
            markup=False,
        )
        yield Static("Starting ROS 2 command…", id="ros-output-status", markup=False)
        with Horizontal(classes="ros-actions"):
            if self._streaming:
                yield Button("Pause", id="ros-pause")
                yield Button("Clear", id="ros-clear")
            yield Button("Close", id="ros-close")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(RichLog).focus()
        if self._streaming:
            self.set_interval(0.15, self._flush_output)
        self._worker = self._run_command()

    def on_screen_suspend(self, event: events.ScreenSuspend) -> None:
        self._worker.cancel()

    @work
    async def _run_command(self) -> None:
        status = self.query_one("#ros-output-status", Static)
        log = self.query_one(RichLog)
        try:
            if self._streaming:
                status.update("Waiting for messages…")
                await self._backend.stream_topic(
                    self._operation, self._target, self._receive, self._message_type
                )
            else:
                output = await self._backend.inspect(self._category, self._operation, self._target)
                log.write(Text(output or "(No output)"), shrink=False)
                status.update("Completed.")
        except Ros2CliError as exc:
            message = str(exc)
            self._flush_output()
            # Keep exit details available even when streaming display is paused.
            log.write(Text(message), shrink=False, scroll_end=log.is_vertical_scroll_end)
            status.update(message.splitlines()[0])

    def _receive(self, line: str, is_error: bool) -> None:
        self._received |= not is_error
        if not self._paused:
            self._pending.append((line, is_error))

    def _flush_output(self) -> None:
        if not self._pending or self._paused:
            return
        log = self.query_one(RichLog)
        batch = Text()
        for line, is_error in self._pending:
            batch.append(line, style="yellow" if is_error else None)
            batch.append("\n")
        self._pending.clear()
        log.write(batch, shrink=False, scroll_end=log.is_vertical_scroll_end)
        if self._worker.is_running and self._received:
            self.query_one("#ros-output-status", Static).update("Streaming…")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        return action == "close" or self._streaming

    def action_pause_output(self) -> None:
        if not self._streaming or not self._worker.is_running:
            return
        if not self._paused:
            self._flush_output()
        self._paused = not self._paused
        self.query_one("#ros-pause", Button).label = "Resume" if self._paused else "Pause"
        status = "Streaming…" if self._received else "Waiting for messages…"
        self.query_one("#ros-output-status", Static).update(
            "Display paused." if self._paused else status
        )

    def action_clear_output(self) -> None:
        self._pending.clear()
        log = self.query_one(RichLog)
        log.clear()
        log.scroll_home(animate=False)

    async def action_close(self) -> None:
        if self._close_requested:
            return
        self._close_requested = True
        self._worker.cancel()
        with suppress(WorkerCancelled):
            await self._worker.wait()
        self.dismiss()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ros-pause":
            self.action_pause_output()
        elif event.button.id == "ros-clear":
            self.action_clear_output()
        elif event.button.id == "ros-close":
            await self.action_close()
