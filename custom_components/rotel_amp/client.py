"""Asyncio TCP client for Rotel amplifiers with automatic reconnect."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import logging
import socket
import time

from .const import (
    CONNECT_TIMEOUT,
    FULL_REFRESH_EVERY,
    HEARTBEAT_INTERVAL,
    POLL_QUERIES,
    RECONNECT_MAX_DELAY,
    RECONNECT_MIN_DELAY,
    STALE_TIMEOUT,
    STATE_QUERIES,
    WRITE_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

UpdateCallback = Callable[[str, str], None]
ConnectionCallback = Callable[[bool], None]


def _enable_keepalive(writer: asyncio.StreamWriter) -> None:
    """Enable TCP keepalive so dead peers (rebooted amp) are detected."""
    sock = writer.get_extra_info("socket")
    if sock is None:
        return
    with contextlib.suppress(OSError, AttributeError):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 10)
        elif hasattr(socket, "TCP_KEEPALIVE"):  # macOS
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPALIVE, 10)
        if hasattr(socket, "TCP_KEEPINTVL"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
        if hasattr(socket, "TCP_KEEPCNT"):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)


def parse_messages(buffer: str) -> tuple[list[tuple[str, str]], str]:
    """Split a raw buffer into (key, value) pairs; return the unparsed rest."""
    *complete, rest = buffer.split("$")
    messages: list[tuple[str, str]] = []
    for chunk in complete:
        for part in chunk.split("\n"):
            part = part.strip()
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            messages.append((key.strip(), value.strip()))
    if len(rest) > 4096:  # garbage without terminators
        rest = ""
    return messages, rest


async def async_test_connection(host: str, port: int) -> None:
    """Open a connection and close it. Raises OSError/TimeoutError on failure."""
    _, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT
    )
    writer.close()
    with contextlib.suppress(Exception):
        await writer.wait_closed()


class RotelClient:
    """Single persistent connection to the amplifier.

    A background task keeps the connection alive: it reconnects with
    exponential backoff, sends a heartbeat when the line is quiet and
    drops the connection if the amp stops answering (e.g. after a reboot).
    """

    def __init__(self, host: str, port: int, poll_interval: float = 0) -> None:
        self.host = host
        self.port = port
        self.poll_interval = poll_interval
        self._last_power: str | None = None
        self._refresh_task: asyncio.Task | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._write_lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._stopping = False
        self._connected = False
        self._update_callbacks: list[UpdateCallback] = []
        self._connection_callbacks: list[ConnectionCallback] = []

    @property
    def connected(self) -> bool:
        """Return True if connected."""
        return self._connected

    def add_update_callback(self, cb: UpdateCallback) -> Callable[[], None]:
        """Register a (key, value) callback."""
        self._update_callbacks.append(cb)
        return lambda: self._update_callbacks.remove(cb)

    def add_connection_callback(self, cb: ConnectionCallback) -> Callable[[], None]:
        """Register a connection state callback."""
        self._connection_callbacks.append(cb)
        return lambda: self._connection_callbacks.remove(cb)

    def start(self, create_task: Callable[..., asyncio.Task]) -> None:
        """Start the background connection loop."""
        self._stopping = False
        if self._task is None or self._task.done():
            self._task = create_task(self._run())

    async def stop(self) -> None:
        """Stop the loop and close the connection."""
        self._stopping = True
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None
        if self._refresh_task:
            self._refresh_task.cancel()
            self._refresh_task = None
        await self._close()
        self._set_connected(False)

    async def send(self, command: str) -> None:
        """Send a raw command. Raises ConnectionError if not connected."""
        writer = self._writer
        if writer is None or writer.is_closing() or not self._connected:
            raise ConnectionError(f"Not connected to Rotel at {self.host}")
        _LOGGER.debug("-> %s", command)
        try:
            async with self._write_lock:
                writer.write(command.encode("ascii"))
                await asyncio.wait_for(writer.drain(), timeout=WRITE_TIMEOUT)
        except (OSError, asyncio.TimeoutError) as err:
            _LOGGER.debug("Write failed (%s), forcing reconnect", err)
            writer.close()  # makes the read loop exit and reconnect
            raise ConnectionError(f"Failed to send {command}: {err}") from err

    async def query_state(self) -> None:
        """Ask the amp for its full current state."""
        await self.query(STATE_QUERIES)

    async def query(self, commands: tuple[str, ...]) -> None:
        """Send a set of query commands."""
        for cmd in commands:
            await self.send(cmd)
            await asyncio.sleep(0.05)

    def _spawn_refresh(self) -> None:
        """Re-query full state in the background (amp needs a moment)."""
        if self._refresh_task and not self._refresh_task.done():
            return

        async def _refresh() -> None:
            await asyncio.sleep(1.0)
            with contextlib.suppress(ConnectionError):
                await self.query_state()

        self._refresh_task = asyncio.create_task(_refresh())

    async def _poll_loop(self) -> None:
        """Periodically re-read volume/power/source while connected.

        The amp normally pushes changes, but pushes can be lost (e.g. a
        change made while it was booting), so values are re-read regularly.
        """
        count = 0
        while True:
            await asyncio.sleep(self.poll_interval)
            count += 1
            try:
                if count % FULL_REFRESH_EVERY == 0:
                    await self.query_state()
                else:
                    await self.query(POLL_QUERIES)
            except ConnectionError as err:
                _LOGGER.debug("Poll failed: %s", err)
                return

    def _set_connected(self, value: bool) -> None:
        if self._connected == value:
            return
        self._connected = value
        for cb in list(self._connection_callbacks):
            try:
                cb(value)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error in connection callback")

    async def _close(self) -> None:
        writer = self._writer
        self._writer = None
        self._reader = None
        if writer is not None:
            writer.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(writer.wait_closed(), timeout=2)

    async def _run(self) -> None:
        delay = RECONNECT_MIN_DELAY
        while not self._stopping:
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=CONNECT_TIMEOUT,
                )
                _enable_keepalive(self._writer)
                _LOGGER.info("Connected to Rotel at %s:%s", self.host, self.port)
                delay = RECONNECT_MIN_DELAY
                self._last_power = None
                self._set_connected(True)
                await self.query_state()
                poll_task = (
                    asyncio.create_task(self._poll_loop())
                    if self.poll_interval > 0
                    else None
                )
                try:
                    await self._read_loop(self._reader)
                finally:
                    if poll_task is not None:
                        poll_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await poll_task
            except asyncio.CancelledError:
                raise
            except (OSError, asyncio.TimeoutError, ConnectionError) as err:
                _LOGGER.debug("Rotel connection error: %s", err)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error in Rotel connection loop")

            await self._close()
            if self._connected:
                _LOGGER.warning(
                    "Lost connection to Rotel at %s:%s, reconnecting",
                    self.host,
                    self.port,
                )
            self._set_connected(False)
            if self._stopping:
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_DELAY)

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        buffer = ""
        last_rx = time.monotonic()
        while not self._stopping:
            try:
                data = await asyncio.wait_for(
                    reader.read(1024), timeout=HEARTBEAT_INTERVAL
                )
            except asyncio.TimeoutError:
                if time.monotonic() - last_rx > STALE_TIMEOUT:
                    raise ConnectionError("Rotel stopped responding") from None
                await self.send("power?")  # heartbeat
                continue
            if not data:
                raise ConnectionError("Connection closed by Rotel")
            last_rx = time.monotonic()
            buffer += data.decode("ascii", errors="ignore")
            messages, buffer = parse_messages(buffer)
            for key, value in messages:
                _LOGGER.debug("<- %s=%s", key, value)
                if key == "power":
                    if value == "on" and self._last_power not in (None, "on"):
                        # just woke up from standby: values may have changed
                        self._spawn_refresh()
                    self._last_power = value
                for cb in list(self._update_callbacks):
                    try:
                        cb(key, value)
                    except Exception:  # noqa: BLE001
                        _LOGGER.exception("Error in update callback")

