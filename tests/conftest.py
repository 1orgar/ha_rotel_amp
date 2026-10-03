"""Fixtures: fake Rotel TCP server."""
from __future__ import annotations

import asyncio

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture(autouse=True)
def allow_localhost(socket_enabled):
    """Real TCP to the in-process fake amp is required."""
    import pytest_socket

    pytest_socket.socket_allow_hosts(["127.0.0.1"], allow_unix_socket=True)


class FakeRotel:
    """Minimal Rotel emulator that can be 'rebooted'."""

    def __init__(self) -> None:
        self.server: asyncio.Server | None = None
        self.port = 0
        self.received: list[str] = []
        self.writers: list[asyncio.StreamWriter] = []
        self.state = {"power": "on", "source": "coax2", "volume": "30", "mute": "off"}

    async def start(self) -> None:
        self.server = await asyncio.start_server(
            self._handle, "127.0.0.1", self.port or 0
        )
        self.port = self.server.sockets[0].getsockname()[1]

    async def reboot(self, downtime: float = 0.3) -> None:
        """Drop everything and come back on the same port."""
        self.server.close()
        for w in self.writers:
            w.close()
        self.writers.clear()
        await self.server.wait_closed()
        await asyncio.sleep(downtime)
        await self.start()

    async def push(self, message: str) -> None:
        """Send an unsolicited update to all clients."""
        for w in self.writers:
            w.write(message.encode())
            await w.drain()

    async def stop(self) -> None:
        self.server.close()
        for w in self.writers:
            w.close()
        await self.server.wait_closed()

    async def _handle(self, reader, writer) -> None:
        self.writers.append(writer)
        buf = ""
        try:
            while data := await reader.read(1024):
                buf += data.decode()
                while True:
                    idx = min((i for i in (buf.find("!"), buf.find("?")) if i >= 0), default=-1)
                    if idx < 0:
                        break
                    cmd, buf = buf[: idx + 1], buf[idx + 1 :]
                    self.received.append(cmd)
                    reply = self._reply(cmd)
                    if reply:
                        writer.write(reply.encode())
                        await writer.drain()
        except (ConnectionError, OSError):
            pass

    mute_replies = False

    def _reply(self, cmd: str) -> str | None:
        if self.mute_replies:
            return None
        name = cmd[:-1]
        if cmd.endswith("?") and name in self.state:
            return f"{name}={self.state[name]}$"
        if name.startswith("vol_") and name[4:].isdigit():
            self.state["volume"] = name[4:]
            return f"volume={self.state['volume']}$"
        if name in ("coax1", "coax2", "opt1", "cd"):
            self.state["source"] = name
            return f"source={name}$"
        return None


@pytest.fixture
async def fake_rotel():
    """Running fake amp."""
    amp = FakeRotel()
    await amp.start()
    yield amp
    await amp.stop()
