"""Assemble the strings.json structure from a language module's texts."""
from __future__ import annotations

from typing import Any


def build(t: dict[str, Any]) -> dict[str, Any]:
    """t = globals() of translations_<lang>.py."""
    text = t["TEXT"]
    address = t["ADDRESS"]
    general = {
        "data": t["GENERAL_DATA"],
        "data_description": t["GENERAL_DESC"],
        "sections": t["GENERAL_SECTIONS"],
    }
    sensors = {k: {"name": v} for k, v in t["ENTITIES"]["sensor"].items()}
    sensors["connection"]["state"] = t["CONNECTION_STATES"]
    return {
        "config": {
            "step": {
                "user": {
                    "title": text["user_title"],
                    "description": text["user_desc"],
                    **address,
                },
                "sources": {
                    "title": text["sources_title"],
                    "description": text["sources_desc"],
                    **general,
                },
                "input": t["INPUT"],
                "announce": t["ANNOUNCE"],
                "reconfigure": {
                    "title": text["reconfigure_title"],
                    "description": text["reconfigure_desc"],
                    "data": {k: address["data"][k] for k in ("host", "port")},
                    "data_description": {
                        k: address["data_description"][k] for k in ("host", "port")
                    },
                },
            },
            "error": t["ERRORS"],
            "abort": {
                "already_configured": text["already_configured"],
                "reconfigure_successful": text["reconfigure_successful"],
            },
        },
        "options": {
            "step": {
                "init": t["MENU"],
                "general": {"title": text["sources_title"], **general},
                "inputs": {
                    "title": text["inputs_title"],
                    "description": text["inputs_desc"],
                    "data": {"sources": text["inputs_field"]},
                },
                "input": t["INPUT"],
                "announce": t["ANNOUNCE"],
            },
            "error": t["ERRORS"],
        },
        "entity": {
            "sensor": sensors,
            **{
                platform: {k: {"name": v} for k, v in names.items()}
                for platform, names in t["ENTITIES"].items()
                if platform != "sensor"
            },
        },
        "issues": {
            "missing_player": {
                "title": text["issue_title"],
                "description": text["issue_desc"],
            }
        },
    }
