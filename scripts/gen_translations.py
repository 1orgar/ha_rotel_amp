"""Build strings.json / translations/{en,ru}.json from one place.

Run: python scripts/gen_translations.py
Texts live in scripts/translations_en.py and scripts/translations_ru.py.
Both files are checked to have exactly the same keys.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
COMP = ROOT / "custom_components" / "rotel_amp"


def _load(lang: str) -> dict:
    path = Path(__file__).with_name(f"translations_{lang}.py")
    spec = importlib.util.spec_from_file_location(f"tr_{lang}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.STRINGS


def _keys(data: dict, prefix: str = "") -> set[str]:
    out: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        out |= _keys(value, path) if isinstance(value, dict) else {path}
    return out


def _write(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    en, ru = _load("en"), _load("ru")
    missing = _keys(en) ^ _keys(ru)
    if missing:
        raise SystemExit(f"en/ru keys differ: {sorted(missing)}")
    _write(COMP / "strings.json", en)
    _write(COMP / "translations" / "en.json", en)
    _write(COMP / "translations" / "ru.json", ru)
    print("ok")


if __name__ == "__main__":
    main()
