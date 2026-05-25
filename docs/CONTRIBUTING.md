# Contributing to TaskChampion MCP

Thank you for your interest in contributing! This document describes the branching model, PR workflow, coding standards, and requirements for all contributions — human and LLM-assisted alike.

---

## License

This project is licensed under the **Apache License, Version 2.0**. By contributing, you agree that your contributions will be licensed under the same terms.

All derivative works and publications that use this code must:
1. Include a copy of the Apache 2.0 license
2. Preserve the `NOTICE` file contents (which credits the original author and repository)
3. State any significant changes made to the original code

See `LICENSE` and `NOTICE` in the repository root.

---

## Branching Model

We use three long-lived branches:

```
main ─── stable releases (tagged with semantic versions)
 ↑
qa ───── integration testing (PRs from dev, validated before main)
 ↑
dev ──── active development (trunk-based for solo work)
```

### For solo development (current phase)
- Work directly on `dev` (trunk-based)
- When ready for release: `dev` → PR to `qa` → test → PR to `main` → tag

### For public contributions
- **Always** branch from `dev`
- Use descriptive branch names:
  - `feature/<short-description>` for new features
  - `fix/<short-description>` for bug fixes
  - `docs/<short-description>` for documentation changes
  - `refactor/<short-description>` for code restructuring
- Open a PR targeting `qa` with:
  - Description of changes
  - Test results (which tests were run, on what environment)
  - Any new assumptions logged (reference `assumptions_and_ideas.md` entries)

### Branch protection rules (to be enforced when repo goes public)
- `main`: requires PR from `qa` only, minimum 1 approval, all tests passing
- `qa`: requires PR, all tests passing
- `dev`: direct push allowed for maintainer, PRs from feature branches for contributors

---

## Pull Request Process

### 1. Create your branch
```bash
git checkout dev
git pull origin dev
git checkout -b feature/my-feature
```

### 2. Make your changes
- Follow the coding standards below
- Add/update tests
- Update documentation if behavior changes
- Log assumptions if applicable (see below)

### 3. Open a PR to `qa`
Include in the PR description:
- **What**: brief summary of the change
- **Why**: link to issue or motivation
- **How**: technical approach taken
- **Testing**: what was tested and how
- **LLM attribution** (if applicable): model and harness used

### 4. Review and merge to `qa`
- At least one human reviewer must approve
- All automated tests must pass
- Reviewer verifies that tests cover the change

### 5. Release to `main`
- When `qa` is validated, create a PR from `qa` to `main`
- The PR to `main` must include:
  - Updated version number (see Semantic Versioning below)
  - Changelog entry
  - Confirmation that all tests pass on `qa`
- After merge, tag the commit: `git tag v<MAJOR>.<MINOR>.<PATCH>`

---

## Semantic Versioning

We follow [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** (`X.0.0`): incompatible API changes (e.g., breaking MCP tool interface changes)
- **MINOR** (`0.X.0`): new features, backward-compatible (e.g., new MCP tools, new schema presets)
- **PATCH** (`0.0.X`): bug fixes, backward-compatible (e.g., fixing a sanitization edge case)

Pre-release versions: `0.x.y` — no stability guarantees until `1.0.0`.

Tags follow the format: `v0.1.0`, `v0.2.0`, etc.

---

## Coding Standards

### Python
- Target Python 3.10+
- Follow PEP 8 style
- Use type hints for all public functions and methods
- Use `ruff` for linting (configuration in `pyproject.toml` when created)
- Use `pytest` for testing

### Documentation
- Markdown for all docs
- TOML for configuration and schema files
- Keep docs in the appropriate subfolder:
  - `docs/adrs/` — architecture decision records
  - `docs/llm_context/` — LLM agent guidelines and assumptions
  - `docs/manuals/` — user and technical manuals
  - `docs/references/` — external tool references
- Update `README.md` when adding new docs

### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `security`

For LLM-assisted commits, add attribution:
```
feat(schemas): add GTD schema preset [LLM: claude-sonnet-4-20250514/Windsurf]
```

---

## Assumption Logging Requirement

**All contributors** (human and LLM) must log unverified assumptions in `docs/llm_context/assumptions_and_ideas.md`. This is especially important for:

- Claims about tool behavior not verified against official docs
- Design decisions based on inferred best practices
- Performance or compatibility assumptions

See `docs/llm_context/AGENTS.md` for the full format. LLM contributors have additional requirements documented there.

---

## Testing Requirements

- Every new feature needs unit tests
- Every bug fix needs a regression test
- Use test fixtures from `tests/fixtures/gold/` (valid data) and `tests/fixtures/problematic/` (edge cases)
- Never delete or weaken existing tests without explicit maintainer approval
- Run the full test suite before submitting a PR:
  ```bash
  uv run pytest
  ```

---

## Security

- Never use `shell=True` in subprocess calls
- Never hardcode secrets or credentials
- Validate all inputs from MCP tool calls before passing to subprocess
- Report security vulnerabilities privately (do not open public issues)
- See ADR 9 for the full security baseline

---

## Getting Help

- Read the docs in `docs/` first
- Check existing ADRs for architectural context
- Open an issue for questions or feature proposals
- For security concerns, contact the maintainer directly

---

*This document was initially generated by Claude claude-sonnet-4-20250514 via Windsurf Cascade. Reviewed by gabiup2, 2026-05-25.*
