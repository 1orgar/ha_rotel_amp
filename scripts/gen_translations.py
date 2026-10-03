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
        "self_player": "Нельзя связать усилитель с самим собой",
        "auto_off": "Автовыключение, если ничего не играет, мин (0 = выкл)",
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
    for section, first in (("config", "sources"), ("options", "init")):
        step = data[section]["step"]["names"]
        step["title"] = t["names_title"]
        step["description"] = t["names_desc"]
        step["data"] = fields
        data[section]["step"][first]["data"]["auto_off"] = t["auto_off"]
        data[section].setdefault("error", {})["self_player"] = t["self_player"]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    sources = _sources()
    _patch(COMP / "strings.json", "en", sources)
    _patch(COMP / "translations" / "en.json", "en", sources)
    _patch(COMP / "translations" / "ru.json", "ru", sources)
    print("ok")


if __name__ == "__main__":
    main()
