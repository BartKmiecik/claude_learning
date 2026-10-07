# pythonProject — Claude Code Learning Path

A series of small Python CLI projects built to learn the Claude Code ecosystem:
CLI fundamentals, agents & subagents, skills & hooks, MCP servers. The curriculum
spec lives in `docs/superpowers/specs/2026-10-07-claude-code-learning-path-design.md`.

## Current focus: Project 1 — `todo` (projects/todo/)

A minimal task manager CLI. Storage: JSON at `~/.todo/tasks.json`.

## Conventions

- Python 3.10, one shared venv at `venv/` (Windows)
- TDD: write the failing test, watch it fail, make it pass (superpowers TDD skill)
- Format with black (a PostToolUse hook runs it automatically on every edit)
- Tests: `venv\Scripts\python.exe -m pytest projects\todo\tests -v`
- Run the CLI: `todo <command>` (installed editable into the venv)
- Commit per plan task with conventional messages (feat:, test:, chore:)

## Known limitations (todo)

- Atomic-save behavior (temp file + os.replace) is implemented but not directly
  unit-tested — hard to assert portably on Windows.
- The store itself does not reject whitespace-only task text; the CLI does.
  Validation lives at the CLI layer by design.
