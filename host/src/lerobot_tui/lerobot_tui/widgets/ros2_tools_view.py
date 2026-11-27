import asyncio

from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, DataTable, OptionList, Select, Static, TabbedContent
from textual.worker import Worker

from lerobot_tui.backends.ros2_cli import (
    UNAVAILABLE,
    Ros2CliBackend,
    Ros2CliError,
    Ros2UnavailableError,
)
from lerobot_tui.models import RosGraphCategory, RosGraphEntity
from lerobot_tui.screens.operation_error import OperationErrorScreen
from lerobot_tui.screens.ros2_command_output import Ros2CommandOutputScreen

CATEGORIES = tuple(RosGraphCategory)
ACTIONS = {
    RosGraphCategory.NODES: ("info",),
    RosGraphCategory.TOPICS: ("info", "echo", "hz", "interface"),
    RosGraphCategory.SERVICES: ("interface",),
    RosGraphCategory.ACTIONS: ("info", "interface"),
}
ACTION_LABELS = {
    "refresh": "Refresh",
    "info": "Info",
    "echo": "Echo",
    "hz": "Hz",
    "interface": "Interface",
}


class Ros2ToolsView(Widget):
    BINDINGS = [
        Binding("left", "category(-1)", show=False, priority=True),
        Binding("right", "category(1)", show=False, priority=True),
        Binding("r", "refresh_graph", "Refresh"),
        Binding("i", "inspect('info')", "Info"),
        Binding("e", "inspect('echo')", "Echo"),
        Binding("h", "inspect('hz')", "Hz"),
        Binding("v", "inspect('interface')", "Interface"),
    ]

    def __init__(self, backend: Ros2CliBackend) -> None:
        super().__init__()
        self._backend = backend
        self._category = RosGraphCategory.NODES
        self._entities: list[RosGraphEntity] = []
        self._selection: dict[RosGraphCategory, tuple[RosGraphEntity, int]] = {}
        self._worker: Worker[None] | None = None
        self._refresh_lock = asyncio.Lock()
        self._loading = False
        self._available = False
        self._error: str | None = None

    def compose(self) -> ComposeResult:
        yield Static("ROS 2 TOOLS", classes="section-title")
        with Horizontal(id="ros-graph"):
            yield OptionList(
                *(category.name.title() for category in CATEGORIES), id="ros-categories"
            )
            with Vertical():
                yield Static("Nodes", id="ros-category-title", classes="section-title")
                yield DataTable(id="ros-table", cursor_type="row", zebra_stripes=True)
                yield Select([], prompt="Interface type", id="ros-type")
        yield Static("", id="ros-graph-status", markup=False)
        with Horizontal(classes="ros-actions"):
            for action, label in ACTION_LABELS.items():
                yield Button(label, id=f"ros-{action}")
            yield Button("Error details", id="ros-error")

    def on_mount(self) -> None:
        self.query_one(OptionList).highlighted = 0
        self.query_one(DataTable).add_column("Name")
        self._update_actions()

    def _is_active(self) -> bool:
        return self.app.query_one("#main-tabs", TabbedContent).active == "ros-tools"

    def set_active(self, active: bool) -> None:
        if active:
            self.query_one(DataTable).focus()
            self.action_refresh_graph()
        elif self._worker is not None:
            self._worker.cancel()

    def action_category(self, step: int) -> None:
        if self.query_one(Select).expanded:
            return
        self._select_category((CATEGORIES.index(self._category) + step) % len(CATEGORIES))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._select_category(event.option_index)

    def _select_category(self, index: int) -> None:
        if not self._is_active():
            return
        self.query_one(OptionList).highlighted = index
        self.query_one(DataTable).focus()
        category = CATEGORIES[index]
        if category == self._category:
            return
        self._remember_selection()
        self._category = category
        self.query_one("#ros-category-title", Static).update(category.name.title())
        self._show_entities([])
        self.action_refresh_graph()

    def _selected(self) -> RosGraphEntity | None:
        row = self.query_one(DataTable).cursor_row
        return self._entities[row] if 0 <= row < len(self._entities) else None

    def _remember_selection(self) -> None:
        if (entity := self._selected()) is not None:
            self._selection[self._category] = (entity, self.query_one(DataTable).cursor_row)

    def action_refresh_graph(self) -> None:
        if not self._is_active():
            return
        self._remember_selection()
        self._available = self._backend.available
        self._error = None
        self._loading = self._available
        self._set_status("Discovering ROS graph entities…" if self._available else UNAVAILABLE)
        if self._worker is not None:
            self._worker.cancel()
        if self._available:
            self._worker = self._refresh_graph(self._category)
        else:
            self._show_entities([])
        self._update_actions()

    @work(group="ros-graph")
    async def _refresh_graph(self, category: RosGraphCategory) -> None:
        async with self._refresh_lock:
            if not self._is_active() or category != self._category:
                return
            try:
                entities = await self._backend.list_entities(category)
            except Ros2UnavailableError:
                self._available = False
                entities = []
                status = UNAVAILABLE
            except Ros2CliError as exc:
                self._error = str(exc)
                entities = []
                status = self._error.splitlines()[0]
            else:
                status = (
                    f"{len(entities)} discovered."
                    if entities
                    else f"No ROS {category.name.lower()} discovered."
                )
            if not self._is_active() or category != self._category:
                return
            self._loading = False
            self._show_entities(entities)
            self._set_status(status)
            self._update_actions()

    def _show_entities(self, entities: list[RosGraphEntity]) -> None:
        self._entities = entities
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_column("Name")
        typed = self._category != RosGraphCategory.NODES
        if typed:
            table.add_column("Type")
        for entity in entities:
            cells = [Text(entity.name)]
            if typed:
                cells.append(Text(", ".join(entity.types) or "(Unavailable)"))
            table.add_row(*cells)

        if entities and self._category in self._selection:
            selected, old_row = self._selection[self._category]
            matching = [row for row, entity in enumerate(entities) if entity == selected]
            if not matching:
                matching = [
                    row for row, entity in enumerate(entities) if entity.name == selected.name
                ]
            if matching:
                table.move_cursor(row=min(matching, key=lambda row: abs(row - old_row)))
        self._update_types()

    def _set_status(self, message: str) -> None:
        self.query_one("#ros-graph-status", Static).update(message)

    def _update_types(self) -> None:
        entity = self._selected()
        types = entity.types if entity is not None else ()
        selector = self.query_one(Select)
        selector.display = len(types) > 1
        if selector.display:
            value = selector.value
            selector.set_options((interface, interface) for interface in types)
            selector.value = value if value in types else types[0]
        self._update_actions()

    def _can_inspect(self, action: str) -> bool:
        entity = self._selected()
        return (
            self._available
            and not self._loading
            and action in ACTIONS[self._category]
            and entity is not None
            and (action != "interface" or bool(entity.types))
        )

    def _update_actions(self) -> None:
        self.query_one("#ros-refresh", Button).disabled = not self._available or self._loading
        for action in ACTIONS[RosGraphCategory.TOPICS]:
            button = self.query_one(f"#ros-{action}", Button)
            button.display = action in ACTIONS[self._category]
            button.disabled = not self._can_inspect(action)
        self.query_one("#ros-error", Button).display = self._error is not None
        self.refresh_bindings()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._update_types()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_inspect(ACTIONS[self._category][0])

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        if not self._is_active():
            return False
        if action == "inspect":
            return self._can_inspect(str(parameters[0]))
        if action == "refresh_graph":
            return self._available and not self._loading
        return True

    def action_inspect(self, action: str) -> None:
        entity = self._selected()
        if not self._is_active() or not self._can_inspect(action) or entity is None:
            return
        selected_type = self.query_one(Select).value
        interface = (
            selected_type
            if selected_type in entity.types
            else (entity.types[0] if entity.types else "")
        )
        topic_type = interface if action == "echo" and len(entity.types) > 1 else ""
        self.app.push_screen(
            Ros2CommandOutputScreen(
                self._backend,
                self._category,
                action,
                interface if action == "interface" else entity.name,
                topic_type,
            )
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = (event.button.id or "").removeprefix("ros-")
        if action == "refresh":
            self.action_refresh_graph()
            self.query_one(DataTable).focus()
        elif action == "error" and self._error:
            self.app.push_screen(OperationErrorScreen("ROS 2 graph discovery", self._error))
        elif action in ACTION_LABELS:
            self.action_inspect(action)
