# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this package is

`stitch-tasks` holds repo-management development tooling for the Stitch uv workspace, written as
[poethepoet](https://poethepoet.natn.io) tasks defined in Python rather than TOML. Python is the
point: tasks can be generated from workspace state, and `@tasks.script` derives a task's full CLI
argument spec from a function signature.

It is the intended successor to the repo-root `Makefile`, which currently carries the whole
lint/test/build/stack surface for the workspace. Read that `Makefile` for the behavior any new task
needs to reproduce.

## Current state

The package is a skeleton. `src/stitch_tasks/__init__.py` holds only a placeholder `main()` wired to
a `stitch-tasks` console script, and there are no tests.

No `[tool.poe]` configuration exists anywhere in the workspace yet, so `poe` reports
`No poe configuration found`. Wiring it is the bootstrap step: add to the **repo-root**
`pyproject.toml`

```toml
[tool.poe]
include_script = "stitch_tasks.tasks:tasks"
```

Poe searches the working directory and its parents for config, so tasks resolve from anywhere in the
workspace once the root file has that block.

## Commands

Run these from the repo root (`/Users/mbarlow/work/stitch`) unless noted.

```bash
uv sync --group dev --all-packages      # sync the workspace venv; needed after dependency changes
uv run poe                              # list tasks (poe lives at .venv/bin/poe)
uv run poe --help <task>                # verify a new task parses and its help reads well
uv run ruff check                       # lint
uv run ruff format                      # format
ty check                                # type check; ty comes from mise, reads root ty.toml
```

Tests, once this package has any, follow the workspace pattern in the `Makefile`:

```bash
uv run --package stitch-tasks --active pytest packages/stitch-tasks
uv run --package stitch-tasks --active pytest packages/stitch-tasks/tests/test_x.py::test_name
```

## Layout and conventions

- **`src/stitch_tasks/tasks.py`** is the public surface: a module-level `TaskCollection` named
  `tasks`. Expect it to become a package (`tasks/__init__.py` exposing the merged collection) as the
  set grows.
- **`src/stitch_tasks/_internal/`** holds everything else. Nothing outside `tasks.py` is public.
  This mirrors the layout of `griffe`, one of this package's own dependencies.
- Prefer small, composable modules over large ones. Build the exported collection by merging
  focused per-area collections with `TaskCollection.include()`.
- **No documentation files and no inline comments.** A task's documentation is its `help` string,
  which `poe` surfaces in the listing and in `poe --help <task>`. If a task needs a comment to be
  understood, rename it, sharpen its `help`, or split it.
- This is internal development tooling. Light test coverage is fine, and error paths do not need
  hardening or defensive handling.
- The flat `src/stitch_tasks/` layout is deliberate. Sibling packages use the namespace layout
  `src/stitch/<name>/`; do not "fix" this one to match.

## Working with TaskCollection

The canonical example is the installed dependency's own definitions, at
`.venv/lib/python3.12/site-packages/poethepoet_tasks/tasks.py`. The detailed reference, including
`@tasks.script` argument inference, `@tasks.generate`, and collection composition, is in the
repo-root skill at `.claude/skills/poethepoet/references/task-packages.md`.

Two rules that bite:

- **Precedence is first-registered-wins per task name.** `include()` appends below what is already
  registered, so to override a task from `poethepoet_tasks`, register your version first, or
  `remove()` then `add()` on the imported collection.
- **Compose, never shell out.** Use `deps`, `uses`, `ref`, or a `sequence`/`parallel` to run one
  task from another. `cmd = "poe other-task"` spawns a second poe process, hides the dependency from
  poe's graph, and cannot reach private `_`-prefixed tasks.

Do not hand-edit dependency arrays in `pyproject.toml`; use `uv add` so `uv.lock` stays in sync.

## Workspace facts worth knowing

- Adding a workspace member requires editing `[tool.uv.workspace] members` in the root
  `pyproject.toml`.
- Python 3.12 is pinned in `.python-version`, `mise.toml`, and `requires-python`.
- `ty.toml` deliberately leaves `environment.root` unset so each member's `tests.*` imports resolve
  against its own package root. The file's comments explain why. Do not set it.
- `griffe` is the import name; the distribution is `griffelib`.
