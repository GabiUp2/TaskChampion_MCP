from __future__ import annotations

import json
from pathlib import Path

import pytest

from taskchampion_mcp.sanitizer import (
    SanitizationError,
    sanitize_annotation,
    sanitize_description,
    sanitize_field_value,
    sanitize_project,
    sanitize_tag,
)

pytestmark = pytest.mark.security


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "problematic"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("entry", _load("injection_attempts.json"))
def test_injection_corpus_is_rejected_by_relevant_sanitizers(entry: dict) -> None:
    attempts = 0
    rejections = 0

    if "description" in entry and isinstance(entry["description"], str):
        attempts += 1
        try:
            sanitize_description(entry["description"])
        except SanitizationError:
            rejections += 1

    if "project" in entry and isinstance(entry["project"], str):
        attempts += 1
        try:
            sanitize_project(entry["project"])
        except SanitizationError:
            rejections += 1

    if "tags" in entry and isinstance(entry["tags"], list):
        attempts += len(entry["tags"])
        for tag in entry["tags"]:
            try:
                sanitize_tag(tag)
            except SanitizationError:
                rejections += 1

    if "annotations" in entry and isinstance(entry["annotations"], list):
        attempts += len(entry["annotations"])
        for ann in entry["annotations"]:
            text = ann.get("description", "")
            try:
                sanitize_annotation(text)
            except SanitizationError:
                rejections += 1

    if "hypothesis" in entry and isinstance(entry["hypothesis"], str):
        attempts += 1
        try:
            sanitize_field_value(entry["hypothesis"], "hypothesis")
        except SanitizationError:
            rejections += 1

    assert attempts > 0, "No relevant sanitizer checks executed for corpus entry"
    assert rejections > 0, "Corpus entry was not rejected by any relevant sanitizer"
