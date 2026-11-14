import unittest

from lerobot_tui.backends.docker import ComposeService
from lerobot_tui.widgets.service_table import ServiceTable
from textual.app import App, ComposeResult


class ServiceTableApp(App[None]):
    def compose(self) -> ComposeResult:
        yield ServiceTable()


class ServiceTableTests(unittest.IsolatedAsyncioTestCase):
    async def test_colored_indicators_state_sorting_and_selection(self) -> None:
        app = ServiceTableApp()
        async with app.run_test() as pilot:
            table = app.query_one(ServiceTable)
            table.update_services(
                [
                    ComposeService("zeta", "Up", "running"),
                    ComposeService("alpha", "Up", "running"),
                    ComposeService("stopped", "Stopped by user", "stopped"),
                    ComposeService("exited", "Exited (0)", "exited"),
                    ComposeService("new", "Not created", "not created"),
                ],
                preferred_service="zeta",
            )
            await pilot.pause()

            ordered_names = sorted(
                ("zeta", "alpha", "stopped", "exited", "new"),
                key=table._sort_key,
            )
            self.assertEqual(
                [table.get_row_index(name) for name in ordered_names],
                list(range(len(ordered_names))),
            )
            self.assertEqual(table.get_selected_service(), "zeta")
            self.assertEqual(table.get_cell("alpha", "indicator").style, "green")
            self.assertEqual(
                table.get_cell("stopped", "indicator").style,
                "red",
            )
            self.assertEqual(
                table.get_cell("exited", "indicator").style,
                "grey70",
            )
            self.assertEqual(
                table.get_cell("new", "indicator").style,
                "grey23",
            )

    async def test_refresh_updates_rows_without_losing_selected_service(self) -> None:
        app = ServiceTableApp()
        async with app.run_test() as pilot:
            table = app.query_one(ServiceTable)
            table.update_services(
                [
                    ComposeService("beta", "Up", "running"),
                    ComposeService("alpha", "Exited", "exited"),
                ]
            )
            table.focus()
            table.move_cursor(row=1, column=0, animate=False)
            selected_key = table.coordinate_to_cell_key((1, 0)).row_key

            table.update_services(
                [
                    ComposeService("beta", "Up 2 minutes", "running"),
                    ComposeService("alpha", "Up 1 minute", "running"),
                    ComposeService("gamma", "Not created", "not created"),
                ]
            )
            await pilot.pause()

            self.assertEqual(table.get_selected_service(), "alpha")
            self.assertEqual(
                table.coordinate_to_cell_key((table.get_row_index("alpha"), 0)).row_key,
                selected_key,
            )
            self.assertEqual(table.get_cell("beta", "status"), "Up 2 minutes")
            self.assertTrue(table.has_focus)


if __name__ == "__main__":
    unittest.main()
