"""Every field / section / menu item shown in the flows has a translation.

Labels are looked up by the frontend exactly like this; a missing key shows
the raw field name (that is how "fixvol_coax2" ended up on screen).
"""
from __future__ import annotations

import json
from pathlib import Path

from homeassistant.data_entry_flow import section
import pytest
import voluptuous as vol

from custom_components.rotel_amp import config_flow as cf

COMP = Path(__file__).resolve().parent.parent / "custom_components" / "rotel_amp"
OPTS = {
    "sources": ["coax2", "opt1"],
    "source_players": {"coax2": "media_player.x"},
}

# step_id -> schema as shown by the flow (worst case: every field visible)
STEPS = {
    "config": {
        "user": cf._address_schema(None, 9590, "Rotel"),
        "sources": cf._general_schema(OPTS),
        "input": cf._input_schema("coax2", OPTS, "media_player.x"),
        "announce": cf._announce_schema(OPTS),
        "reconfigure": cf._address_schema("h", 9590, None),
    },
    "options": {
        "general": cf._general_schema(OPTS),
        "input": cf._input_schema("coax2", OPTS, "media_player.x"),
        "announce": cf._announce_schema(OPTS),
        "inputs": vol.Schema({vol.Required("sources"): str}),
    },
}


def _fields(schema: vol.Schema):
    for key, value in schema.schema.items():
        if isinstance(value, section):
            yield str(key), [str(k) for k in value.schema.schema]
        else:
            yield str(key), None


@pytest.mark.parametrize("lang", ["strings", "en", "ru"])
def test_every_flow_field_is_translated(lang: str) -> None:
    path = COMP / ("strings.json" if lang == "strings" else f"translations/{lang}.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    missing: list[str] = []
    for flow, steps in STEPS.items():
        for step_id, schema in steps.items():
            step = data[flow]["step"].get(step_id)
            if step is None:
                missing.append(f"{flow}.step.{step_id}")
                continue
            for name, sub in _fields(schema):
                if sub is None:
                    if name not in step.get("data", {}):
                        missing.append(f"{flow}.{step_id}.data.{name}")
                    if name not in step.get("data_description", {}):
                        missing.append(f"{flow}.{step_id}.data_description.{name}")
                    continue
                sec = step.get("sections", {}).get(name, {})
                if "name" not in sec:
                    missing.append(f"{flow}.{step_id}.sections.{name}.name")
                for field in sub:
                    if field not in sec.get("data", {}):
                        missing.append(f"{flow}.{step_id}.sections.{name}.data.{field}")
                    if field not in sec.get("data_description", {}):
                        missing.append(
                            f"{flow}.{step_id}.sections.{name}.data_description.{field}"
                        )
    menu = data["options"]["step"]["init"]
    for option in ("general", "inputs", "announce", "save"):
        if option not in menu.get("menu_options", {}):
            missing.append(f"options.init.menu_options.{option}")
    # "inputs" has no description per field on purpose
    missing = [m for m in missing if m != "options.inputs.data_description.sources"]
    assert not missing, missing


def test_translations_have_same_keys() -> None:
    def keys(d: dict, p: str = "") -> set[str]:
        out: set[str] = set()
        for k, v in d.items():
            out |= keys(v, f"{p}.{k}") if isinstance(v, dict) else {f"{p}.{k}"}
        return out

    en = json.loads((COMP / "translations/en.json").read_text(encoding="utf-8"))
    ru = json.loads((COMP / "translations/ru.json").read_text(encoding="utf-8"))
    strings = json.loads((COMP / "strings.json").read_text(encoding="utf-8"))
    assert keys(en) == keys(ru)
    assert en == strings
