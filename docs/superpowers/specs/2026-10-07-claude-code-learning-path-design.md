# Claude Code Learning Path — Design

**Date:** 2026-10-07
**Status:** Approved (brainstorming sections 1–3)

## 1. Purpose

The user is brand new to Claude Code and wants to learn the full ecosystem — CLI fundamentals, agents & subagents, skills & hooks, and MCP servers — by building real Python CLI tools. Each project teaches one concept area in a focused sandbox; the same disciplined workflow (brainstorm → spec → plan → test-driven implementation → review → finish) repeats every time so the process becomes second nature.

A PDF course summary is produced at the end (project 5), containing the curriculum, per-project step-by-step guides, and a concept reference.

## 2. Learner Profile & Constraints

- **Experience:** Brand new to Claude Code; comfortable with Python (PyCharm, Python 3.10 venv on Windows 11).
- **Time budget:** Medium — roughly 4–10 hours per project.
- **Project style:** Python CLI & automation tools.
- **Environment:** `C:\Users\user\Projects\Python\pythonProject`, currently **not a git repository**. Git is initialized at the root as part of this plan (the superpowers workflow depends on git).
- **Installed tooling:** superpowers skill plugin (brainstorming, writing-plans, executing-plans, TDD, code review, worktrees, etc.).

## 3. Curriculum

| # | Project | What you build | Concepts learned | ~Time |
|---|---------|---------------|-------------------|-------|
| 1 | `todo` | Task manager CLI | Git setup, CLAUDE.md, permissions, memory, slash commands, plan→code→test→review loop, first hook | 4–6h |
| 2 | `filesweeper` | File organizer (categorize/dedupe/dry-run) | Plan mode, parallel subagents, code review workflow, git worktrees | 6–8h |
| 3 | `devlog` | Dev journal generator + first custom skill | Designing/building custom skills, hooks automation, settings.json, plugin packaging | 6–8h |
| 4 | `apibuddy` | MCP server giving Claude a new external tool | MCP protocol, tool schemas, connecting Claude Code to external services | 6–8h |
| 5 | `pdf-summary` | Script that generates the course summary PDF | Everything combined — full workflow applied to a real deliverable | 4–6h |

**Progression logic:** Each project's topic gets more advanced, but the process stays identical. By project 3 the workflow is muscle memory; the novelty is the concept itself.

**Disk layout:** one subfolder per project under the repo root:

```
pythonProject/
  projects/todo/
  projects/filesweeper/
  projects/devlog/
  projects/apibuddy/
  projects/pdf-summary/
  docs/
    superpowers/specs/      # design docs (one per project, as reached)
    pdfs/                   # markdown sources for the course PDF
```

**Specification rhythm:** Projects 2–4 each get their own brainstorming + spec + plan when we reach them; this document designs the curriculum and project 1 in full detail, and sketches 2–5.

## 4. Project 1: `todo` — Task Manager CLI (Detailed Design)

**Goal:** a minimal but real CLI; the point is the *workflow*, not the features.

### 4.1 Commands

```
$ todo add "learn claude code"     # → #1 added: learn claude code
$ todo list                        # → 1. [ ] learn claude code
$ todo done 1                      # → #1 completed
$ todo list                        # → 1. [x] learn claude code
$ todo remove 1                    # → #1 removed
```

Exactly four subcommands: `add`, `list`, `done`, `remove`. No flags, no due dates, no priorities (YAGNI — later projects can extend it).

### 4.2 Architecture

```
projects/todo/
  pyproject.toml        # pytest + black as dev deps; `todo` console script entry point
  todo_cli/
    __init__.py
    cli.py              # argparse, subcommand dispatch, output formatting
    store.py            # JSON persistence: add/list/done/remove
  tests/
    test_store.py       # storage logic unit tests
    test_cli.py         # CLI behavior tests (call main(argv), capture output)
```

**Boundaries:** `cli.py` knows nothing about JSON; `store.py` knows nothing about argparse. Each module is testable alone. `main(argv) -> int` returns the exit code so tests can assert on it.

**Storage:** `~/.todo/tasks.json` (user home dir), directory created on first use. Task shape: `{id: int, text: str, done: bool, created_at: str}`. IDs are sequential integers; `done` toggles true, `remove` deletes.

**Atomic saves:** write to a temp file in the same directory, then `os.replace()` — a crash can never corrupt the task list.

### 4.3 Error Handling

| Case | Behavior |
|------|----------|
| `add` with empty text | message on stderr, exit 1 |
| `done`/`remove` with unknown id | "No task #N" on stderr, exit 1 |
| Corrupt JSON file | clear error naming the file path, exit 1 |
| Success | exit 0 |

### 4.4 Testing

pytest, test-first (superpowers TDD: red → green → refactor). Both modules unit-tested, happy paths and error paths: add/list/done/remove round-trips, persistence across store reloads, unknown-id errors, corrupt-file error, atomic-save behavior.

### 4.5 Claude Code Curriculum for Project 1

1. **Git setup:** `git init` at repo root, first commit.
2. **CLAUDE.md:** written together — Claude's persistent project memory (purpose, conventions, commands).
3. **The pipeline:** `/superpowers:brainstorming` → `/superpowers:writing-plans` → `/superpowers:executing-plans` (with TDD + verification-before-completion) → `/code-review` → finish & commit.
4. **Permissions:** approve/deny tool calls live; learn what each permission means.
5. **Memory:** Claude saves durable user preferences; the user sees when and why.
6. **First hook:** one PostToolUse hook that runs `black` on any edited `.py` file. Enough to see hooks fire in real time. (Project 3 goes deep on hooks.)

### 4.6 Success Criteria

- All four commands work against a persistent store.
- pytest suite green.
- A code review happened.
- The user can name each Claude Code concept used.

## 5. Projects 2–4 (Sketches — full specs later)

- **`filesweeper` (agents & subagents):** categorize files by type into folders, detect duplicates, `--dry-run` preview. Multiple independent modules (categorization rules, duplicate finder, plan/execute engine) developed in parallel by subagents, using plan mode, git worktrees, and the requesting/receiving code review skills.
- **`devlog` (skills & hooks):** a CLI that generates a dev journal / release notes from git history, plus a custom skill packaging it, deeper hooks (PreToolUse permission guards, Stop notification), and settings.json management via the update-config skill.
- **`apibuddy` (MCP):** a Python MCP server (stdio transport, JSON-RPC) exposing an external API — e.g., GitHub repos/issues or weather — as tools Claude Code can call. Registered via `claude mcp add`. Tool schema design and error handling are the focus.

## 6. Project 5: `pdf-summary` — Course Summary PDF (Detailed Design)

### 6.1 PDF Contents

1. **Curriculum map** — the 5 projects, what each taught, in order.
2. **Per-project chapters** — what was built, step-by-step instructions, "concepts learned" box.
3. **Concept reference** — agents, subagents, skills, hooks, MCP, permissions: each explained through how the user *actually used it*.

### 6.2 Generation

- **Content lives in markdown files** under `docs/pdfs/` (e.g., `01-todo.md`), written after each project finishes. Content and rendering stay separate — updating the PDF means editing markdown and re-running.
- **`projects/pdf-summary/` converts markdown → PDF** using **reportlab** (pure Python, no system dependencies, reliable on Windows; weasyprint rejected — needs GTK on Windows).
- Renderer features: title page, table of contents, headings/paragraphs/code blocks/tables, page numbers.

### 6.3 How It's Built (the capstone)

The full workflow applied at once: plan the converter; develop chapter renderers as independent modules via parallel subagents; TDD the renderer (headings render, tables wrap, page breaks correct); hooks fire on every edit; final code review. The output document itself is the proof of everything learned.

### 6.4 Success Criteria

One command (`python -m pdf_summary`) produces a well-formatted PDF from the markdown sources, containing all project chapters.

## 7. Cross-Cutting Process Rules

- Every project follows: brainstorm → spec → plan → implement (TDD) → verify → code review → finish.
- Verification before completion: run tests and show output before claiming anything works.
- Dependencies added per project only when needed.
- All commands in this document use the venv at the repo root (`venv\Scripts\python.exe`).
