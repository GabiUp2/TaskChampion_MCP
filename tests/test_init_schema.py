from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from taskchampion_mcp.config import ServerConfig
from taskchampion_mcp.init_schema import (
    _confirm,
    _build_parser,
    _print_presets,
    _prompt,
    _resolve_role,
    _run_generate_branch,
    _run_preset_branch,
    main,
    run_init,
)


def test_resolve_role_uses_requested_value() -> None:
    assert _resolve_role("manager", non_interactive=False, already_configured=False) == "MANAGER"


def test_resolve_role_invalid_requested_exits() -> None:
    with pytest.raises(SystemExit):
        _resolve_role("invalid-role", non_interactive=False, already_configured=False)


def test_resolve_role_non_interactive_without_request() -> None:
    assert _resolve_role(None, non_interactive=True, already_configured=False) is None


def test_resolve_role_interactive_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taskchampion_mcp.init_schema._prompt", lambda *_a, **_kw: "2")
    assert _resolve_role(None, non_interactive=False, already_configured=False) == "GENERATOR"


def test_prompt_and_confirm_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter(["", "yes", ""])
    monkeypatch.setattr("builtins.input", lambda _p: next(answers))
    assert _prompt("Q", default="x") == "x"
    assert _confirm("Q", default_yes=False) is True
    assert _confirm("Q", default_yes=True) is True


def test_run_generate_branch_fails_without_tasks_or_taxonomy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taskchampion_mcp.init_schema.load_config", lambda: ServerConfig())
    monkeypatch.setattr("taskchampion_mcp.init_schema.resolve_taxonomy_path", lambda **_kw: None)
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.analyze_existing_tasks",
        lambda _task_cli: {"success": True, "task_count": 0},
    )

    ok = _run_generate_branch(
        task_cli=MagicMock(),
        project_dir=None,
        taxonomy_path=None,
        output_path=None,
        schema_name=None,
        role="CONTRIBUTOR",
        non_interactive=True,
    )
    assert ok is False


def test_run_generate_branch_preview_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taskchampion_mcp.init_schema.load_config", lambda: ServerConfig())
    monkeypatch.setattr("taskchampion_mcp.init_schema.resolve_taxonomy_path", lambda **_kw: None)
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.analyze_existing_tasks",
        lambda _task_cli: {"success": True, "task_count": 1},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.generate_schema_preview",
        lambda **_kw: {"error": True, "message": "boom"},
    )

    ok = _run_generate_branch(
        task_cli=MagicMock(),
        project_dir=None,
        taxonomy_path=None,
        output_path=None,
        schema_name=None,
        role="CONTRIBUTOR",
        non_interactive=True,
    )
    assert ok is False


def test_run_generate_branch_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "generated.toml"
    monkeypatch.setattr("taskchampion_mcp.init_schema.load_config", lambda: ServerConfig())
    monkeypatch.setattr("taskchampion_mcp.init_schema.resolve_taxonomy_path", lambda **_kw: None)
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.analyze_existing_tasks",
        lambda _task_cli: {"success": True, "task_count": 1},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.generate_schema_preview",
        lambda **_kw: {"success": True, "schema_toml": '[meta]\nname = "x"\n'},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.save_initial_schema",
        lambda **_kw: {
            "success": True,
            "schema_path": str(out),
            "config_file": str(tmp_path / "config.toml"),
            "role": "CONTRIBUTOR",
        },
    )

    ok = _run_generate_branch(
        task_cli=MagicMock(),
        project_dir=None,
        taxonomy_path=None,
        output_path=str(out),
        schema_name=None,
        role="CONTRIBUTOR",
        non_interactive=True,
    )
    assert ok is True


def test_run_generate_branch_interactive_taxonomy_override_and_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    detected = tmp_path / "TAXONOMY.md"
    detected.write_text("# tax", encoding="utf-8")
    out = tmp_path / "generated.toml"
    out.write_text("old", encoding="utf-8")

    monkeypatch.setattr("taskchampion_mcp.init_schema.load_config", lambda: ServerConfig())
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.resolve_taxonomy_path",
        lambda **_kw: detected,
    )
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.analyze_existing_tasks",
        lambda _task_cli: {"success": True, "task_count": 1},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.generate_schema_preview",
        lambda **_kw: {"success": True, "schema_toml": '[meta]\nname = "x"\n'},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.save_initial_schema",
        lambda **_kw: {
            "success": True,
            "schema_path": str(out),
            "config_file": str(tmp_path / "config.toml"),
            "role": "CONTRIBUTOR",
        },
    )

    confirms = iter([False, True])
    prompts = iter([str(tmp_path / "missing.md")])
    monkeypatch.setattr("taskchampion_mcp.init_schema._confirm", lambda *_a, **_kw: next(confirms))
    monkeypatch.setattr("taskchampion_mcp.init_schema._prompt", lambda *_a, **_kw: next(prompts))

    ok = _run_generate_branch(
        task_cli=MagicMock(),
        project_dir=None,
        taxonomy_path=None,
        output_path=str(out),
        schema_name=None,
        role="CONTRIBUTOR",
        non_interactive=False,
    )
    assert ok is True


def test_run_preset_branch_requires_name_in_noninteractive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.list_preset_schemas",
        lambda: {"presets": [{"name": "minimal", "description": "d"}]},
    )
    ok = _run_preset_branch(
        preset_name=None,
        taxonomy_path=None,
        copy=False,
        output_path=None,
        role=None,
        non_interactive=True,
    )
    assert ok is False


def test_run_preset_branch_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.list_preset_schemas",
        lambda: {"presets": [{"name": "minimal", "description": "d"}]},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.use_preset_schema",
        lambda **_kw: {
            "success": True,
            "preset_name": "minimal",
            "copied_to": str(tmp_path / "schema.toml"),
            "config_file": str(tmp_path / "config.toml"),
            "role": "GENERATOR",
        },
    )

    ok = _run_preset_branch(
        preset_name="minimal",
        taxonomy_path=None,
        copy=True,
        output_path=str(tmp_path / "schema.toml"),
        role="GENERATOR",
        non_interactive=True,
    )
    assert ok is True


def test_run_preset_branch_interactive_invalid_numeric_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.list_preset_schemas",
        lambda: {"presets": [{"name": "minimal", "description": "d"}]},
    )
    monkeypatch.setattr("taskchampion_mcp.init_schema._prompt", lambda *_a, **_kw: "99")
    ok = _run_preset_branch(
        preset_name=None,
        taxonomy_path=None,
        copy=False,
        output_path=None,
        role=None,
        non_interactive=False,
    )
    assert ok is False


def test_print_presets_false_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taskchampion_mcp.init_schema.list_preset_schemas", lambda: {"presets": []})
    assert _print_presets() is False


def test_print_presets_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.list_preset_schemas",
        lambda: {"schema_dir": "/tmp/schemas", "presets": [{"name": "minimal", "description": "d"}]},
    )
    assert _print_presets() is True


def test_run_init_list_presets_short_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taskchampion_mcp.init_schema._print_presets", lambda: True)
    assert run_init(list_presets=True) is True


def test_run_init_already_initialised_non_interactive_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("taskchampion_mcp.init_schema.load_config", lambda: ServerConfig())
    monkeypatch.setattr("taskchampion_mcp.init_schema.TaskwarriorCLI", lambda **_kw: MagicMock())
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.get_initialization_status",
        lambda **_kw: {
            "needs_onboarding": False,
            "custom_schema_path": "/tmp/schema.toml",
            "taxonomy_path": None,
            "role_configured": True,
        },
    )
    assert run_init(non_interactive=True) is False


def test_run_init_calls_preset_branch_when_preset_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taskchampion_mcp.init_schema.load_config", lambda: ServerConfig())
    monkeypatch.setattr("taskchampion_mcp.init_schema.TaskwarriorCLI", lambda **_kw: MagicMock())
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.get_initialization_status",
        lambda **_kw: {"needs_onboarding": True, "role_configured": False},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema._resolve_role",
        lambda *_a, **_kw: "CONTRIBUTOR",
    )
    called: dict[str, bool] = {"preset": False}

    def _preset(**_kwargs):
        called["preset"] = True
        return True

    monkeypatch.setattr("taskchampion_mcp.init_schema._run_preset_branch", _preset)
    assert run_init(preset="minimal", non_interactive=True) is True
    assert called["preset"] is True


def test_run_init_calls_generate_branch_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("taskchampion_mcp.init_schema.load_config", lambda: ServerConfig())
    monkeypatch.setattr("taskchampion_mcp.init_schema.TaskwarriorCLI", lambda **_kw: MagicMock())
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema.get_initialization_status",
        lambda **_kw: {"needs_onboarding": True, "role_configured": False},
    )
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema._resolve_role",
        lambda *_a, **_kw: "CONTRIBUTOR",
    )
    called: dict[str, bool] = {"generate": False}

    def _generate(**_kwargs):
        called["generate"] = True
        return True

    monkeypatch.setattr("taskchampion_mcp.init_schema._run_generate_branch", _generate)
    assert run_init(non_interactive=True) is True
    assert called["generate"] is True


def test_build_parser_understands_flags() -> None:
    parser = _build_parser()
    args = parser.parse_args(["--preset", "minimal", "--role", "MANAGER", "--non-interactive"])
    assert args.preset == "minimal"
    assert args.role == "MANAGER"
    assert args.non_interactive is True


def test_main_exits_zero_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    args = argparse.Namespace(
        project_dir=None,
        taxonomy=None,
        output=None,
        name=None,
        preset=None,
        role=None,
        list_presets=False,
        copy_preset=False,
        non_interactive=True,
    )
    monkeypatch.setattr(
        "taskchampion_mcp.init_schema._build_parser",
        lambda: SimpleNamespace(parse_args=lambda: args),
    )
    monkeypatch.setattr("taskchampion_mcp.init_schema.run_init", lambda **_kw: True)

    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
