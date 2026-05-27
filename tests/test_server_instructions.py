from taskchampion_mcp.config import Role, ServerConfig
from taskchampion_mcp.schema import TaskSchema
from taskchampion_mcp.server import _build_instructions


def _render(role: str) -> str:
    cfg = ServerConfig(role=role)
    schema = TaskSchema(name="minimal", version="1.0.0")
    return _build_instructions(cfg, schema, "3.99.0", onboarding_required=False)


def test_contributor_instructions_include_write_surface() -> None:
    instructions = _render(Role.CONTRIBUTOR)
    assert "READ, ANNOTATE, MODIFY, START, and STOP" in instructions
    assert "CANNOT create new tasks or complete/delete them" in instructions


def test_generator_instructions_include_start_stop_plus_create() -> None:
    instructions = _render(Role.GENERATOR)
    assert "READ, ANNOTATE, MODIFY, START, STOP, and CREATE" in instructions
    assert "CANNOT complete or delete tasks" in instructions

