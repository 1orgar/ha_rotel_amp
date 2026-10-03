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
        "refvol": "{0}: relative volume for matching (0 = off)",
        "keepon": "{0}: never auto power off on this input",
        "self_player": "Cannot link the amplifier to itself",
        "auto_off": "Auto power off when nothing plays, min (0 = off)",
        "announce_source": "Input for announcements (TTS)",
        "announce_volume": "Announcement volume, % of the scale (0 = keep current)",
        "announce_needs_player": "The announcement input needs a linked media player",
        "names_desc_extra": (
            " Relative volume: amp levels that sound equally loud on different "
            "inputs, e.g. Player 40 and Alice 20. On an input change the volume is "
            "scaled by their ratio."
        ),
        "reconfigure_title": "Change amplifier address",
        "reconfigure_desc": "New IP address or port. Inputs and links are kept.",
        "reconfigure_successful": "Address updated",
        "unique_id_mismatch": "Another amplifier is already configured at this address",
        "issue_title": "Linked media player not found",
        "issue_desc": (
            "{title}: these linked media players no longer exist: {players}. "
            "Open the integration → Configure and pick other players or clear "
            "the fields."
        ),
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
        "refvol": "{0}: относительная громкость для подстройки (0 = выкл)",
        "keepon": "{0}: не выключать автоматически на этом входе",
        "self_player": "Нельзя связать усилитель с самим собой",
        "auto_off": "Автовыключение, если ничего не играет, мин (0 = выкл)",
        "announce_source": "Вход для объявлений (TTS)",
        "announce_volume": "Громкость объявлений, % шкалы (0 = не менять)",
        "announce_needs_player": "У входа для объявлений должен быть связанный media player",
        "names_desc_extra": (
            " Относительная громкость — уровни усилителя, при которых разные входы "
            "звучат одинаково громко, например Плеер 40 и Алиса 20. При смене "
            "входа громкость пересчитывается по их отношению."
        ),
        "reconfigure_title": "Изменить адрес усилителя",
        "reconfigure_desc": "Новый IP-адрес или порт. Входы и связи сохранятся.",
        "reconfigure_successful": "Адрес обновлён",
        "unique_id_mismatch": "По этому адресу уже настроен другой усилитель",
        "issue_title": "Связанный media player не найден",
        "issue_desc": (
            "{title}: эти связанные плееры больше не существуют: {players}. "
            "Откройте интеграцию → «Настроить» и выберите другие плееры или "
            "очистите поля."
        ),
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
        "number": {"bass": "Bass", "treble": "Treble", "balance": "Balance"},
        "switch": {"speaker_a": "Speakers A", "speaker_b": "Speakers B",
                   "bypass": "Tone bypass"},
        "select": {"dimmer": "Display dimmer", "pcusb_class": "PC-USB audio class"},
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
        "number": {"bass": "Низкие частоты", "treble": "Высокие частоты",
                   "balance": "Баланс"},
        "switch": {"speaker_a": "Колонки A", "speaker_b": "Колонки B",
                   "bypass": "Обход тембров"},
        "select": {"dimmer": "Яркость дисплея", "pcusb_class": "Класс PC-USB аудио"},
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
        fields[f"refvol_{key}"] = t["refvol"].format(default)
        fields[f"keepon_{key}"] = t["keepon"].format(default)
    fields["announce_source"] = t["announce_source"]
    fields["announce_volume"] = t["announce_volume"]
    for section, first in (("config", "sources"), ("options", "init")):
        step = data[section]["step"]["names"]
        step["title"] = t["names_title"]
        step["description"] = t["names_desc"] + t["names_desc_extra"]
        step["data"] = fields
        data[section]["step"][first]["data"]["auto_off"] = t["auto_off"]
        errors = data[section].setdefault("error", {})
        errors["self_player"] = t["self_player"]
        errors["announce_needs_player"] = t["announce_needs_player"]
    e = ENTITY[lang]
    config = data["config"]
    config["error"]["no_response"] = e["no_response"]
    config["step"]["reconfigure"] = {
        "title": t["reconfigure_title"],
        "description": t["reconfigure_desc"],
        "data": dict(config["step"]["user"]["data"]),
    }
    config["step"]["reconfigure"]["data"].pop("name", None)
    config.setdefault("abort", {})["reconfigure_successful"] = t["reconfigure_successful"]
    config["abort"]["unique_id_mismatch"] = t["unique_id_mismatch"]
    sensors = {k: {"name": v} for k, v in e["sensor"].items()}
    sensors["connection"]["state"] = e["connection_state"]
    data["entity"] = {
        "sensor": sensors,
        **{
            platform: {k: {"name": v} for k, v in e[platform].items()}
            for platform in ("button", "number", "switch", "select")
        },
    }
    data["issues"] = {
        "missing_player": {"title": t["issue_title"], "description": t["issue_desc"]}
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
