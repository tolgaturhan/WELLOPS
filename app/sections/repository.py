from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class SectionTemplateRef:
    template_key: str
    version: int


def _templates_dir() -> Path:
    # app/sections/repository.py -> app/sections/templates
    return Path(__file__).resolve().parent / "templates"


def template_path(template_key: str, version: int) -> Path:
    return _templates_dir() / f"{template_key}.v{version}.json"


def load_template(template_key: str, version: int) -> Dict[str, Any]:
    path = template_path(template_key, version)
    if not path.exists():
        raise FileNotFoundError(f"Section template file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)