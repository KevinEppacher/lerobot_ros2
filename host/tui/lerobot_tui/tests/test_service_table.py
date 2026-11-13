import unittest

from lerobot_tui.backends.docker import ComposeService
from lerobot_tui.widgets.service_table import ServiceTable
from textual.app import App, ComposeResult


class ServiceTableApp(App[None]):
    def compose(self) -> ComposeResult:
        yield ServiceTable()


class ServiceTableTests(unittest.IsolatedAsyncioTestCase):
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

            self.assertEqual(table.get_selected_service(), "beta")
            self.assertEqual(table.coordinate_to_cell_key((1, 0)).row_key, selected_key)
            self.assertEqual(table.get_cell("beta", "status"), "Up 2 minutes")
            self.assertTrue(table.has_focus)


if __name__ == "__main__":
    unittest.main()
