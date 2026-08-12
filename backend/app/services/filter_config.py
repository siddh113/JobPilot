"""Reads/writes just the `filters:` block in config.yaml, using ruamel.yaml
so the rest of the file's comments and structure survive an edit — a plain
pyyaml load+dump would silently strip every comment in the file, including
the explanatory ones already in config.yaml.
"""
from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config.yaml"

DEFAULT_FILTERS = {
    "max_days_since_posted": None,
    "remote_only": False,
    "exclude_keywords": [],
    "require_keywords": [],
}


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def load_filters() -> dict:
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_FILTERS)
    y = _yaml()
    with open(CONFIG_PATH) as f:
        data = y.load(f)
    return dict(data.get("filters", DEFAULT_FILTERS)) if data else dict(DEFAULT_FILTERS)


def save_filters(filters: dict) -> None:
    y = _yaml()
    with open(CONFIG_PATH) as f:
        data = y.load(f)
    if data is None:
        raise FileNotFoundError(f"{CONFIG_PATH} is empty or missing — run initial setup first.")
    data["filters"] = filters
    with open(CONFIG_PATH, "w") as f:
        y.dump(data, f)
