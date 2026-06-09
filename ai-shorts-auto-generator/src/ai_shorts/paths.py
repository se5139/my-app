from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PROJECTS_DIR = DATA_DIR / "projects"
GROWTH_DIR = DATA_DIR / "growth"
APP_STATE_PATH = DATA_DIR / "app_state.json"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    GROWTH_DIR.mkdir(parents=True, exist_ok=True)
