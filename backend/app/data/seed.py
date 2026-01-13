import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SEED_PATH = Path(__file__).resolve().parent / "seed.json"


@lru_cache(maxsize=1)
def load_seed() -> dict[str, Any]:
    with SEED_PATH.open(encoding="utf-8-sig") as f:
        return json.load(f)


def get_projects() -> list[dict[str, Any]]:
    return list(load_seed().get("projects", []))


def get_members() -> list[dict[str, Any]]:
    return list(load_seed().get("members", []))


def find_project(project_id: str) -> dict[str, Any] | None:
    return next((p for p in get_projects() if p.get("id") == project_id), None)


def find_members(member_ids: list[str]) -> list[dict[str, Any]]:
    wanted = set(member_ids)
    return [m for m in get_members() if m.get("id") in wanted]
