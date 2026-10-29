from __future__ import annotations

from pathlib import Path

from poethepoet_tasks import TaskCollection

from ._internal.griffe import api_surface_markdown, directory_surface_markdown

tasks = TaskCollection()


def _emit(markdown: str, output: str, stem: str) -> None:
    path = Path(output) if output else Path("docs") / f"{stem}-api-surface.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    print(path)


@tasks.script(
    help="Write a module's public top-level API surface as markdown",
    tags=["docs"],
)
def api_surface(module: str, *, output: str = "") -> None:
    _emit(api_surface_markdown(module), output, module.rsplit(".", 1)[-1])


@tasks.script(
    help="Write every module under a directory as one markdown API surface",
    tags=["docs"],
)
def api_surface_tree(directory: str, *, output: str = "") -> None:
    _emit(
        directory_surface_markdown(directory),
        output,
        Path(directory).resolve().name,
    )
