# Project 1: todo — Task Manager CLI

## What We Built

A minimal task manager CLI with four commands: `add`, `list`, `done`, `remove`.
Tasks persist as JSON at `~/.todo/tasks.json` with atomic writes (temp file +
os.replace). Two modules with a clean boundary: `store.py` owns persistence,
`cli.py` owns argument parsing and output. 21 tests, all green.

## Step by Step

1. **Skeleton** — `pyproject.toml` with a `todo` console script and dev deps
   (pytest, black), installed editable into the venv; `CLAUDE.md` written for
   the repo.
2. **First hook** — a PostToolUse hook in `.claude/settings.json` that runs
   black on every edited `.py` file (stdin JSON → `tool_input.file_path`).
3. **Store, test-first** — wrote failing tests, watched them fail, implemented:
   `add`/`list` first, then `done`/`remove`, plus `StoreError` for corrupt
   files and a review-fix that validates every JSON element.
4. **CLI, test-first** — argparse with `main(argv, store_path)` injectable for
   tests; exact output formats; errors on stderr with exit code 1.
5. **Verify & finish** — full suite, real smoke test against `~/.todo`,
   code review with fixes, this chapter.

## Concepts Learned

- **The pipeline**: brainstorm → spec → plan → implement (TDD) → review → finish.
- **CLAUDE.md**: Claude's persistent project memory — conventions and commands.
- **Permissions**: approving/denying tool calls and what each prompt means.
- **Hooks**: PostToolUse fires after every Edit/Write; reads tool JSON from
  stdin; exit codes control feedback. PostToolUse can never block.
- **Subagents**: each plan task was implemented and reviewed by fresh
  subagents — implementer, spec reviewer, code quality reviewer.
- **TDD discipline**: red → green → refactor, one commit per task.

## Files

- `projects/todo/pyproject.toml`, `projects/todo/todo_cli/{store,cli}.py`
- `projects/todo/tests/{test_store,test_cli}.py`, `.claude/settings.json`
- `CLAUDE.md`
