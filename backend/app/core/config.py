from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "config.yaml"

# Secrets (ANTHROPIC_API_KEY, etc.) live in a root-level .env, never
# committed — see CLAUDE.md §0.6. The Anthropic SDK reads
# ANTHROPIC_API_KEY straight from the environment, so this just needs to
# land in os.environ before any `Anthropic()` client gets constructed.
load_dotenv(ROOT / ".env")


@lru_cache
def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Missing {CONFIG_PATH}. Copy config.example.yaml to config.yaml and fill in your details."
        )
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    resume_path = ROOT / cfg["resume_path"]
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume file not found: {resume_path}")
    cfg["_resume_text"] = resume_path.read_text()

    return cfg
