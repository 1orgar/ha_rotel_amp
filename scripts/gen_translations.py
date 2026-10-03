"""Regenerate per-input field labels in strings.json / translations.

Run: python scripts/gen_translations.py
Input fields are dynamic (name_<input>, player_<input>), so their labels are
generated from const.SOURCES.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMP = ROOT / "custom_components" / "rotel_amp"


def _sources() -> dict[str, str]:
    """Read SOURCES {key: default name} from const.py without importing HA."""
    tree = ast.parse((COMP / "const.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "SOURCES":
            value = ast.literal_eval(node.value)
            return {k: v[2] for k, v in value.items()}
    raise RuntimeError("SOURCES not found")


TEXT = {
    "en": {
        "names_title": "Input names and linked players",
        "names_desc": (
            "Give the inputs meaningful names (e.g. Coax 2 → Streamer). "
            "Optionally link a media player to an input: while that input is "
            "selected, the amplifier entity shows its track info and artwork and "
            "passes play/pause/next/seek/browse to it. Volume, power and input "
            "always stay on the amplifier. With \"switch to this input\" enabled, "
            "the amplifier turns on and selects the input when the player starts "
            "playing, and other linked players are paused."
        ),
        "name": "{0}: name",
        "player": "{0}: linked media player",
        "follow": "{0}: switch to this input when the player starts playing",
        "fixvol": "{0}: keep the player volume at 100 %",
        "self_player": "Cannot link the amplifier to itself",
        "auto_off": "Auto power off when nothing plays, min (0 = off)",
    },
    "ru": {
        "names_title": "Названия входов и связанные плееры",
        "names_desc": (
            "Задайте понятные названия (например, Coax 2 → Стример). "
            "К входу можно привязать media player: пока выбран этот вход, "
            "плеер усилителя показывает трек и обложку и передаёт ему "
            "play/pause/next/перемотку/обзор медиа. Громкость, питание и вход "
            "всегда управляются усилителем. Если включено «переключаться на этот "
            "вход», то когда плеер начинает играть, усилитель включается и "
            "выбирает этот вход, а другие связанные плееры ставятся на паузу."
        ),
        "name": "{0}: название",
        "player": "{0}: связанный media player",
        "follow": "{0}: переключаться на этот вход, когда плеер начинает играть",
        "fixvol": "{0}: держать громкость плеера на 100 %",
        "self_player": "Нельзя связать усилитель с самим собой",
        "auto_off": "Автовыключение, если ничего не играет, мин (0 = выкл)",
    },
}


ENTITY = {
    "en": {
        "sensor": {
            "model": "Model",
            "firmware": "Firmware",
            "pc_usb_firmware": "PC-USB firmware",
            "ip_address": "IP address",
            "mac_address": "MAC address",
            "latency": "Response time",
            "connection": "Connection",
            "connected_since": "Connected since",
            "last_message": "Last message",
            "reconnects": "Reconnects",
            "last_error": "Last connection error",
        },
        "button": {"test_connection": "Test connection"},
        "connection_state": {"connected": "Connected", "disconnected": "Disconnected"},
        "no_response": "The device is reachable but does not answer Rotel commands",
    },
    "ru": {
        "sensor": {
            "model": "Модель",
            "firmware": "Прошивка",
            "pc_usb_firmware": "Прошивка PC-USB",
            "ip_address": "IP-адрес",
            "mac_address": "MAC-адрес",
            "latency": "Время ответа",
            "connection": "Соединение",
            "connected_since": "Подключён с",
            "last_message": "Последнее сообщение",
            "reconnects": "Переподключения",
            "last_error": "Последняя ошибка соединения",
        },
        "button": {"test_connection": "Проверить соединение"},
        "connection_state": {"connected": "Подключено", "disconnected": "Отключено"},
        "no_response": "Устройство доступно, но не отвечает на команды Rotel",
    },
}


def _patch(path: Path, lang: str, sources: dict[str, str]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    t = TEXT[lang]
    fields: dict[str, str] = {}
    for key, default in sources.items():
        fields[f"name_{key}"] = t["name"].format(default)
        fields[f"player_{key}"] = t["player"].format(default)
        fields[f"follow_{key}"] = t["follow"].format(default)
        fields[f"fixvol_{key}"] = t["fixvol"].format(default)
    for section, first in (("config", "sources"), ("options", "init")):
        step = data[section]["step"]["names"]
        step["title"] = t["names_title"]
        step["description"] = t["names_desc"]
        step["data"] = fields
        data[section]["step"][first]["data"]["auto_off"] = t["auto_off"]
        data[section].setdefault("error", {})["self_player"] = t["self_player"]
    e = ENTITY[lang]
    data["config"]["error"]["no_response"] = e["no_response"]
    sensors = {k: {"name": v} for k, v in e["sensor"].items()}
    sensors["connection"]["state"] = e["connection_state"]
    data["entity"] = {
        "sensor": sensors,
        "button": {k: {"name": v} for k, v in e["button"].items()},
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    sources = _sources()
    _patch(COMP / "strings.json", "en", sources)
    _patch(COMP / "translations" / "en.json", "en", sources)
    _patch(COMP / "translations" / "ru.json", "ru", sources)
    print("ok")


if __name__ == "__main__":
    main()
