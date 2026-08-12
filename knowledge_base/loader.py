"""
Loads TechnologyProfile JSON files from disk and validates every one
against the schema. A malformed hand-written profile should fail here,
loudly, at load time — not silently corrupt a score downstream.
"""

import json
from pathlib import Path

from schemas.technology_profile import TechnologyProfile

KB_ROOT = Path(__file__).parent


def load_department(department: str) -> list[TechnologyProfile]:
    dept_dir = KB_ROOT / department
    if not dept_dir.exists():
        raise FileNotFoundError(f"No knowledge base directory for department: {department}")

    profiles = []
    for file in sorted(dept_dir.glob("*.json")):
        data = json.loads(file.read_text())
        try:
            profiles.append(TechnologyProfile.model_validate(data))
        except Exception as e:
            raise ValueError(f"Invalid profile in {file.name}: {e}") from e

    return profiles
