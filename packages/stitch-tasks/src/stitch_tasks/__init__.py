from __future__ import annotations

from pathlib import Path

from poethepoet_tasks import TaskCollection

from stitch_tasks.griffe import api_surface_markdown

__all__ = ["api_surface", "main", "tasks"]

tasks = TaskCollection()


@tasks.script(
    help="Write a module's public top-level API surface as markdown",
    tags=["docs"],
)
def api_surface(module: str, *, output: str = "") -> None:
    markdown = api_surface_markdown(module)
    if output:
        Path(output).write_text(markdown, encoding="utf-8")
    else:
        print(markdown)


def main() -> None:
    print("Hello from stitch-tasks!")
