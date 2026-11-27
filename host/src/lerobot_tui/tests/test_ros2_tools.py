import asyncio
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from textual.widgets import Button, DataTable, RichLog, Select, Static, TabbedContent

from lerobot_tui.app import LeRobotApp
from lerobot_tui.backends.ros2_cli import (
    Ros2CliBackend,
    Ros2CliError,
    Ros2UnavailableError,
)
from lerobot_tui.models import RosGraphCategory, RosGraphEntity
from lerobot_tui.screens.ros2_command_output import Ros2CommandOutputScreen

FAKE_CLI = r"""
import os
import signal
import sys
import time
from pathlib import Path

category, action, *args = sys.argv[1:]
if "/stream_error" in args:
    sys.exit("stream failure details")
elif "/stream_exit" in args:
    sys.exit(0)
elif action in {"echo", "hz"} or "/slow" in args:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path(os.environ["TEST_PID_FILE"]).write_text(str(os.getpid()))
    while True:
        print("  data: [literal markup]")
        print("stream diagnostic", file=sys.stderr)
        time.sleep(0.03)
elif "/fail" in args:
    sys.exit("failure details")
elif "missing/msg/Unknown" in args:
    sys.exit("Unknown package 'missing'")
elif action == "list":
    print({
        "node": "    /node\n/node\nWARNING: something\ninvalid",
        "topic": " /topic [std_msgs/msg/String, std_msgs/msg/Bool]\n"
                 "bad [ ]\n/unknown []\n/other [malformed",
        "service": "/service [std_srvs/srv/Empty]",
        "action": os.getenv("TEST_ACTIONS", ""),
    }[category])
else:
    print("  info: [literal markup]")
"""


class Ros2ToolsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        resources = ExitStack()
        self.addCleanup(resources.close)
        directory = resources.enter_context(tempfile.TemporaryDirectory())
        self.pid_file = Path(directory, "pid")
        executable = Path(directory, "ros2")
        executable.write_text(f"#!{sys.executable}\n{FAKE_CLI}")
        executable.chmod(0o755)
        resources.enter_context(
            patch.dict(
                os.environ,
                {"PATH": directory, "TEST_PID_FILE": str(self.pid_file)},
            )
        )
        self.backend = Ros2CliBackend()
        self.backend.TERMINATION_TIMEOUT = 0.08

    async def wait_for(self, condition) -> None:
        async def poll() -> None:
            while not condition():
                await asyncio.sleep(0.02)

        await asyncio.wait_for(poll(), 3)

    def assert_reaped(self) -> None:
        pid = int(self.pid_file.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.pid_file.unlink()

    async def test_listings_and_finite_commands(self) -> None:
        expected = {
            RosGraphCategory.NODES: [RosGraphEntity("/node")] * 2,
            RosGraphCategory.TOPICS: [
                RosGraphEntity("/topic", ("std_msgs/msg/String", "std_msgs/msg/Bool")),
                RosGraphEntity("/unknown"),
            ],
            RosGraphCategory.SERVICES: [RosGraphEntity("/service", ("std_srvs/srv/Empty",))],
            RosGraphCategory.ACTIONS: [],
        }
        for category, entities in expected.items():
            with self.subTest(category=category):
                self.assertEqual(await self.backend.list_entities(category), entities)

        self.assertEqual(
            await self.backend.inspect(RosGraphCategory.NODES, "info", "/node"),
            "  info: [literal markup]\n",
        )
        with self.assertRaisesRegex(Ros2CliError, "failure details"):
            await self.backend.inspect(RosGraphCategory.NODES, "info", "/fail")
        with self.assertRaisesRegex(Ros2CliError, "Interface type support unavailable"):
            await self.backend.inspect(RosGraphCategory.TOPICS, "interface", "missing/msg/Unknown")

        with patch.dict(
            os.environ, {"TEST_ACTIONS": "/action [example_interfaces/action/Fibonacci]"}
        ):
            self.assertEqual(
                await self.backend.list_entities(RosGraphCategory.ACTIONS),
                [RosGraphEntity("/action", ("example_interfaces/action/Fibonacci",))],
            )
            self.assertIn(
                "info:",
                await self.backend.inspect(RosGraphCategory.ACTIONS, "info", "/action"),
            )

    async def test_missing_cli(self) -> None:
        with patch.dict(os.environ, {"PATH": ""}):
            self.assertFalse(self.backend.available)
            with self.assertRaises(Ros2UnavailableError):
                await self.backend.list_entities(RosGraphCategory.NODES)
            app = self.make_app()
            async with app.run_test() as pilot:
                await pilot.press("4")
                self.assertIn(
                    "unavailable", str(app.query_one("#ros-graph-status", Static).render())
                )
                self.assertTrue(app.query_one("#ros-refresh", Button).disabled)
                await pilot.press("2")
                self.assertEqual(app.query_one(TabbedContent).active, "services")

    async def test_timeout_kills_and_reaps(self) -> None:
        self.backend.COMMAND_TIMEOUT = 0.3
        with self.assertRaisesRegex(Ros2CliError, "timed out"):
            await self.backend.inspect(RosGraphCategory.NODES, "info", "/slow")
        self.assert_reaped()

    async def test_cancelled_stream_kills_and_reaps(self) -> None:
        received = []
        stream = asyncio.create_task(
            self.backend.stream_topic("echo", "/topic", lambda *line: received.append(line))
        )
        await self.wait_for(lambda: len(received) >= 2)
        stream.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await stream
        self.assertIn(("  data: [literal markup]", False), received)
        self.assertIn(("stream diagnostic", True), received)
        self.assert_reaped()

    async def test_stream_reports_failure_and_unexpected_exit(self) -> None:
        def discard(line: str, is_error: bool) -> None:
            pass

        with self.assertRaisesRegex(Ros2CliError, "stream failure details"):
            await self.backend.stream_topic("echo", "/stream_error", discard)
        with self.assertRaisesRegex(Ros2CliError, "exited unexpectedly"):
            await self.backend.stream_topic("hz", "/stream_exit", discard)

    def make_app(self) -> LeRobotApp:
        app = LeRobotApp()
        app._docker = None
        app._ros = self.backend
        return app

    async def test_navigation_output_and_shutdown(self) -> None:
        app = self.make_app()
        async with app.run_test(size=(80, 24)) as pilot:
            for key, pane in zip(
                "123564",
                ("dashboard", "services", "robots", "wifi", "settings", "ros-tools"),
                strict=True,
            ):
                await pilot.press(key)
                self.assertEqual(app.query_one(TabbedContent).active, pane)

            table = app.query_one("#ros-table", DataTable)
            await self.wait_for(lambda: table.row_count == 2)
            self.assertTrue(app.query_one("#ros-info", Button).display)
            self.assertFalse(app.query_one("#ros-echo", Button).display)
            await pilot.press("down", "r")
            await self.wait_for(lambda: not app.query_one("#ros-refresh", Button).disabled)
            self.assertEqual(table.cursor_row, 1)
            await pilot.press("enter")
            self.assertIsInstance(app.screen, Ros2CommandOutputScreen)
            log = app.screen.query_one(RichLog)
            await self.wait_for(lambda log=log: bool(log.lines))
            self.assertIn("  info: [literal markup]", log.lines[0].text)
            await pilot.press("q", "right")
            await self.wait_for(lambda: table.row_count == 2 and len(table.columns) == 2)
            self.assertTrue(app.query_one("#ros-type", Select).display)
            self.assertTrue(app.query_one("#ros-echo", Button).display)
            self.assertTrue(app.query_one("#ros-hz", Button).display)

            for shortcut in ("e", "h"):
                await pilot.press(shortcut)
                self.assertIsInstance(app.screen, Ros2CommandOutputScreen)
                log = app.screen.query_one(RichLog)
                await self.wait_for(lambda log=log: bool(log.lines))
                await pilot.press("p", "c")
                await pilot.pause(0.25)
                self.assertFalse(log.lines)
                await pilot.press("p")
                await self.wait_for(lambda log=log: bool(log.lines))
                await pilot.press("escape")
                self.assertNotIsInstance(app.screen, Ros2CommandOutputScreen)
                self.assert_reaped()

            await pilot.press("right")
            await self.wait_for(lambda: table.row_count == 1)
            self.assertFalse(app.query_one("#ros-info", Button).display)
            self.assertTrue(app.query_one("#ros-interface", Button).display)
            await pilot.press("right")
            await self.wait_for(
                lambda: "No ROS actions" in str(app.query_one("#ros-graph-status", Static).render())
            )
            await pilot.press("left", "left")
            await self.wait_for(lambda: table.row_count == 2)
            await pilot.press("e")
            await self.wait_for(self.pid_file.exists)
        self.assert_reaped()
