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
        self.state = {
            "power": "on",
            "source": "coax2",
            "volume": "30",
            "mute": "off",
            "model": "RA-1572",
            "version": "V1.4.3",
            "mac": "00:11:22:33:44:55",
            "freq": "off",
            "bass": "000",
            "treble": "000",
            "balance": "000",
            "speaker": "a",
            "dimmer": "0",
            "bypass": "off",
        }
        self.signals = {}
        self.ignore_source_commands = 0  # simulate amp booting

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
        self.writers.clear()
        try:
            await asyncio.wait_for(self.server.wait_closed(), 2)
        except TimeoutError:
            pass

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
        if cmd == "ip?":
            return "ipaddress=127.0.0.1$"
        if cmd.endswith("?") and name in self.state:
            return f"{name}={self.state[name]}$"
        if name == "power_on":
            self.state["power"] = "on"
            return "power=on$"
        if name == "power_off":
            self.state["power"] = "standby"
            return "power=standby$"
        if name.startswith("vol_") and name[4:].isdigit():
            self.state["volume"] = str(int(name[4:]))
            return f"volume={self.state['volume']}$"
        if name in ("coax1", "coax2", "opt1", "cd"):
            if self.ignore_source_commands > 0:
                self.ignore_source_commands -= 1
                return None
            self.state["source"] = name
            # signal disappears on input change until the test sets it again
            self.state["freq"] = self.signals.get(name, "off")
            return f"source={name}$"
        for tone in ("bass", "treble"):
            if name.startswith(f"{tone}_"):
                self.state[tone] = name.split("_", 1)[1]
                return f"{tone}={self.state[tone]}$"
        if name.startswith("balance_"):
            value = name.split("_", 1)[1].upper()
            self.state["balance"] = value
            return f"balance={value}$"
        if name.startswith("speaker_") and name.endswith(("_on", "_off")):
            side, onoff = name.split("_")[1:3]
            on = set(self.state.get("speaker", "").replace("off", "").split("_")) - {""}
            on = on | {side} if onoff == "on" else on - {side}
            self.state["speaker"] = "_".join(sorted(on)) or "off"
            return f"speaker={self.state['speaker']}$"
        if name.startswith("dimmer_"):
            self.state["dimmer"] = name.split("_", 1)[1]
            return f"dimmer={self.state['dimmer']}$"
        if name in ("bypass_on", "bypass_off"):
            self.state["bypass"] = name.split("_")[1]
            return f"bypass={self.state['bypass']}$"
        return None

    # sample rate reported per input (missing = no signal)
    signals: dict[str, str] = {}


@pytest.fixture
async def fake_rotel():
    """Running fake amp."""
    amp = FakeRotel()
    await amp.start()
    yield amp
    await amp.stop()
