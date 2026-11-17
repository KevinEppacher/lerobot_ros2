import subprocess
from pathlib import Path

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

SETTINGS_LOGO = r"""
   _____      __  __  _
  / ___/___  / /_/ /_(_)___  ____ ______
  \__ \/ _ \/ __/ __/ / __ \/ __ `/ ___/
 ___/ /  __/ /_/ /_/ / / / / /_/ (__  )
/____/\___/\__/\__/_/_/ /_/\__, /____/
                          /____/
""".strip("\n")


class SettingsView(Widget):
    BINDINGS = [
        ("backspace", "go_back", "Parent Directory"),
    ]

    def __init__(self, directory: Path) -> None:
        super().__init__()

        self._root = directory.resolve()
        self._directory = self._root
        self._entries: list[Path] = []

    def compose(self) -> ComposeResult:
        yield Static(
            SETTINGS_LOGO,
            id="settings-logo",
            markup=False,
        )

        yield Static("SETTINGS", classes="section-title")

        yield Static("", id="settings-path")

        yield OptionList(id="settings-files")

        yield Button(
            "Open with nano",
            id="edit-settings",
            variant="primary",
        )

        yield Static(
            "Enter: Open | Backspace: Parent directory",
            id="settings-status",
        )

    def on_mount(self) -> None:
        self._refresh_files()

    def _refresh_files(self) -> None:
        entries = sorted(
            (
                path
                for path in self._directory.iterdir()
                if path.resolve().is_relative_to(self._root)
            ),
            key=lambda path: (not path.is_dir(), path.name.lower()),
        )

        self._entries = entries

        options = [
            Option(
                f"{'[DIR]' if path.is_dir() else '[FILE]'} {path.name}",
                id=str(index),
            )
            for index, path in enumerate(entries)
        ]

        option_list = self.query_one("#settings-files", OptionList)
        option_list.set_options(options)

        relative = self._directory.relative_to(self._root)

        self.query_one("#settings-path", Static).update(f"Directory: docker/deploy/{relative}")

    def on_option_list_option_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        self._open_selected()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit-settings":
            self._open_selected()

    def on_key(self, event) -> None:
        if event.key == "backspace":
            self._go_back()
            event.stop()

    def _go_back(self) -> None:
        if self._directory == self._root:
            return

        self._directory = self._directory.parent
        self._refresh_files()

    def _open_selected(self) -> None:
        option_list = self.query_one("#settings-files", OptionList)

        if option_list.highlighted is None:
            return

        index = option_list.highlighted

        if index >= len(self._entries):
            return

        path = self._entries[index]

        if not path.resolve().is_relative_to(self._root):
            self.notify("Access outside deployment directory denied.")
            return

        if path.is_dir():
            self._directory = path.resolve()
            self._refresh_files()
            return

        if not path.is_file():
            return

        try:
            with self.app.suspend():
                subprocess.run(
                    ["nano", str(path)],
                    cwd=self._directory,
                    check=True,
                )

            self.query_one("#settings-status", Static).update(f"Closed editor: {path.name}")

        except (OSError, subprocess.CalledProcessError) as exc:
            self.notify(
                f"Cannot open editor: {exc}",
                severity="error",
            )

    def action_go_back(self) -> None:
        self._go_back()
