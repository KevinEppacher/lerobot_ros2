import asyncio
import codecs
import os
import re
import shlex
import shutil
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress

from lerobot_tui.models import RosGraphCategory, RosGraphEntity

UNAVAILABLE = (
    "ROS 2 CLI is unavailable in the current environment. "
    "Launch the TUI through the Pixi host environment to use ROS 2 tools."
)
GRAPH_NAME = r"/[\w]+(?:/[\w]+)*"
TYPED_ENTITY = re.compile(rf"({GRAPH_NAME})\s+\[([^\[\]]*)\]")
INTERFACE_TYPE = re.compile(r"\w+/(?:msg/|srv/|action/)?\w+")
StreamOutput = Callable[[str, bool], None]


class Ros2CliError(RuntimeError):
    pass


class Ros2UnavailableError(Ros2CliError):
    pass


class Ros2CliBackend:
    COMMAND_TIMEOUT = 10.0
    TERMINATION_TIMEOUT = 1.0

    def __init__(self) -> None:
        self._running: set[asyncio.Task[None]] = set()

    @property
    def available(self) -> bool:
        return shutil.which("ros2") is not None

    async def list_entities(self, category: RosGraphCategory) -> list[RosGraphEntity]:
        args = [category.value, "list"]
        if category != RosGraphCategory.NODES:
            args.append("-t")
        # Jazzy's action verbs do not expose the direct discovery option.
        if category != RosGraphCategory.ACTIONS:
            args.append("--no-daemon")
        output = await self._execute(tuple(args))
        return self._parse_listing(category, output)

    @staticmethod
    def _parse_listing(category: RosGraphCategory, output: str) -> list[RosGraphEntity]:
        entities = []
        for line in output.splitlines():
            line = line.strip()
            if category == RosGraphCategory.NODES:
                if re.fullmatch(GRAPH_NAME, line):
                    entities.append(RosGraphEntity(line))
                continue

            match = TYPED_ENTITY.fullmatch(line)
            if match:
                name, types = match.groups()
                interfaces = tuple(
                    dict.fromkeys(
                        interface
                        for item in types.split(",")
                        if (interface := item.strip()) and INTERFACE_TYPE.fullmatch(interface)
                    )
                )
                entities.append(RosGraphEntity(name, interfaces))
        return entities

    @staticmethod
    def _inspection_args(
        category: RosGraphCategory, action: str, target: str, message_type: str = ""
    ) -> tuple[str, ...]:
        if action == "interface" and INTERFACE_TYPE.fullmatch(target):
            return ("interface", "show", target)
        if not re.fullmatch(GRAPH_NAME, target):
            raise ValueError(f"Invalid ROS graph name: {target}")
        if action == "info":
            if category == RosGraphCategory.NODES:
                return ("node", "info", target, "--no-daemon")
            if category == RosGraphCategory.TOPICS:
                return ("topic", "info", target, "--verbose", "--no-daemon")
            if category == RosGraphCategory.ACTIONS:
                return ("action", "info", target)
        if category == RosGraphCategory.TOPICS:
            if action == "echo":
                if message_type and not INTERFACE_TYPE.fullmatch(message_type):
                    raise ValueError(f"Invalid ROS message type: {message_type}")
                types = (message_type,) if message_type else ()
                return ("topic", "echo", target, *types, "--no-daemon")
            if action == "hz":
                return ("topic", "hz", target)
        raise ValueError(f"Unsupported ROS 2 inspection: {category.value} {action}")

    def preview(
        self, category: RosGraphCategory, action: str, target: str, message_type: str = ""
    ) -> str:
        return shlex.join(("ros2", *self._inspection_args(category, action, target, message_type)))

    async def inspect(
        self, category: RosGraphCategory, action: str, target: str, message_type: str = ""
    ) -> str:
        if action not in {"info", "interface"}:
            raise ValueError(f"Unsupported ROS 2 inspection: {action}")
        return await self._execute(
            self._inspection_args(category, action, target, message_type), include_stderr=True
        )

    async def stream_topic(
        self, action: str, topic: str, emit: StreamOutput, message_type: str = ""
    ) -> None:
        args = self._inspection_args(RosGraphCategory.TOPICS, action, topic, message_type)
        if action not in {"echo", "hz"}:
            raise ValueError(f"Unsupported ROS 2 stream: {action}")

        async with self._process(args) as process:
            assert process.stdout is not None and process.stderr is not None

            async def drain(reader: asyncio.StreamReader, is_error: bool) -> str:
                decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
                pending = ""
                tail = ""
                while chunk := await reader.read(4096):
                    decoded = decoder.decode(chunk)
                    tail = (tail + decoded)[-4096:]
                    pending += decoded
                    lines = pending.split("\n")
                    pending = lines.pop()
                    for line in lines:
                        emit(line.removesuffix("\r"), is_error)
                    if len(pending) >= 4096:
                        emit(pending, is_error)
                        pending = ""
                remainder = decoder.decode(b"", final=True)
                if pending or remainder:
                    emit(pending + remainder, is_error)
                return tail + remainder

            readers = (
                asyncio.create_task(drain(process.stdout, False)),
                asyncio.create_task(drain(process.stderr, True)),
            )
            try:
                stdout_tail, stderr_tail = await asyncio.gather(*readers)
                code = await process.wait()
            finally:
                for reader in readers:
                    reader.cancel()
                await asyncio.gather(*readers, return_exceptions=True)

            self._check(args, code, stderr_tail, stdout_tail)
            raise Ros2CliError("ROS 2 streaming command exited unexpectedly (exit code 0).")

    async def _execute(self, args: tuple[str, ...], *, include_stderr: bool = False) -> str:
        async with self._process(args) as process:
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), self.COMMAND_TIMEOUT)
            except asyncio.TimeoutError as exc:
                raise Ros2CliError(
                    f"ROS 2 command timed out after {self.COMMAND_TIMEOUT:g}s.\n"
                    f"{shlex.join(('ros2', *args))}"
                ) from exc

            output = stdout.decode(errors="replace")
            diagnostics = stderr.decode(errors="replace")
            self._check(args, process.returncode, diagnostics, output)
            if include_stderr and diagnostics:
                separator = "\n" if output and not output.endswith("\n") else ""
                return output + separator + diagnostics
            return output

    @staticmethod
    def _check(args: tuple[str, ...], code: int, stderr: str, stdout: str) -> None:
        if code == 0:
            return
        details = "\n".join(part for part in (stderr.strip(), stdout.strip()) if part)
        missing_interface = args[0] == "interface" or "passed message type is invalid" in details
        reason = (
            "Interface type support unavailable" if missing_interface else "ROS 2 command failed"
        )
        raise Ros2CliError(
            f"{reason} (exit code {code}).\n{shlex.join(('ros2', *args))}\n{details}".rstrip()
        )

    @asynccontextmanager
    async def _process(self, args: tuple[str, ...]) -> AsyncIterator[asyncio.subprocess.Process]:
        started = asyncio.create_task(
            asyncio.create_subprocess_exec(
                "ros2",
                *args,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
        )
        # Keep ownership even when cancellation arrives while the process is spawning.
        finished = asyncio.get_running_loop().create_future()
        cleanup = asyncio.create_task(self._cleanup(started, finished))
        self._running.add(cleanup)
        cleanup.add_done_callback(self._running.discard)
        try:
            try:
                process = await asyncio.shield(started)
            except FileNotFoundError as exc:
                raise Ros2UnavailableError(UNAVAILABLE) from exc
            except OSError as exc:
                raise Ros2CliError(f"ROS 2 command could not start: {exc}") from exc
            yield process
        finally:
            finished.set_result(None)
            await asyncio.shield(cleanup)

    async def _cleanup(
        self, started: asyncio.Task[asyncio.subprocess.Process], finished: asyncio.Future[None]
    ) -> None:
        await finished
        try:
            process = await started
        except OSError:
            return

        async def discard(reader: asyncio.StreamReader) -> None:
            while await reader.read(65536):
                pass

        assert process.stdout is not None and process.stderr is not None
        drained = asyncio.gather(discard(process.stdout), discard(process.stderr), process.wait())
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.terminate()
        try:
            await asyncio.wait_for(asyncio.shield(drained), self.TERMINATION_TIMEOUT)
        except asyncio.TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
            await drained

    async def wait_for_cleanup(self) -> None:
        await asyncio.gather(*self._running)
