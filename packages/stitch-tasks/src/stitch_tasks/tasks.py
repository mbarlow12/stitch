from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from poethepoet_tasks import TaskCollection

from ._internal.griffe import (
    DEFAULT_EXCLUDES,
    api_surface_markdown,
    directory_surface_markdown,
)
from ._internal.workspace import resolve_package

tasks = TaskCollection()


def _surface_args(target: str, target_help: str) -> list[dict]:
    return [
        {"name": target, "positional": True, "required": True, "help": target_help},
        {
            "name": "output",
            "options": ["-o", "--output"],
            "default": "",
            "help": "Destination path, defaults to docs/<name>-api-surface.md",
        },
    ]


def _path_args() -> list[dict]:
    return [
        {
            "name": "exclude",
            "options": ["-x", "--exclude"],
            "multiple": True,
            "help": (
                "File or directory names to skip, in addition to dotted names "
                f"and {', '.join(DEFAULT_EXCLUDES)}"
            ),
        },
    ]


def _emit(markdown: str, output: str, stem: str) -> None:
    path = Path(output) if output else Path("docs") / f"{stem}-api-surface.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    print(path)


@tasks.script(
    help="Write a module's public top-level API surface as markdown",
    task_args=False,
    options={"args": _surface_args("module", "Importable module path")},
    tags=["docs"],
)
def api_surface(module: str, *, output: str = "") -> None:
    _emit(api_surface_markdown(module), output, module.rsplit(".", 1)[-1])


@tasks.script(
    help="Write every module under a directory as one markdown API surface",
    task_args=False,
    options={
        "args": [
            *_surface_args("directory", "Directory of modules to walk"),
            *_path_args(),
        ]
    },
    tags=["docs"],
)
def api_surface_tree(
    directory: str, *, output: str = "", exclude: Sequence[str] = ()
) -> None:
    _emit(
        directory_surface_markdown(directory, exclude),
        output,
        Path(directory).resolve().name,
    )


@tasks.script(
    help="Write a package's whole API surface as one markdown file",
    task_args=False,
    options={
        "args": [
            *_surface_args("package", "Installed package name, or a path in one"),
            *_path_args(),
        ]
    },
    tags=["docs"],
)
def api_package(package: str, *, output: str = "", exclude: Sequence[str] = ()) -> None:
    name, directory = resolve_package(package)
    _emit(
        directory_surface_markdown(
            str(directory), exclude, title=name, heading_base=directory
        ),
        output,
        name,
    )
