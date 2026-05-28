from __future__ import annotations

import json
from pathlib import Path


def test_gold_dataset_includes_all_schema_presets() -> None:
    fixtures_dir = Path(__file__).resolve().parent / "fixtures" / "gold"
    expected = {
        "minimal_tasks.json",
        "gtd_tasks.json",
        "scrum_tasks.json",
        "kanban_tasks.json",
        "authors_custom_tasks.json",
    }
    existing = {p.name for p in fixtures_dir.glob("*_tasks.json")}
    assert expected.issubset(existing)


def test_gold_dataset_files_are_valid_json_arrays() -> None:
    fixtures_dir = Path(__file__).resolve().parent / "fixtures" / "gold"
    for path in fixtures_dir.glob("*_tasks.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, list), path.name
        assert payload, path.name
