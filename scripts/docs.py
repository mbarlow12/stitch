from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from griffe_surface import api_surface_markdown, directory_surface_markdown
from uv_workspace import resolve_package, workspace_packages

FRONTEND_ROOT = Path("deployments") / "stitch-frontend"


def emit(markdown: str, output: str, stem: str, kind: str) -> None:
    path = Path(output) if output else Path("docs") / f"{stem}-{kind}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    print(path)


kind, target, *rest = sys.argv[1:]

if kind == "module":
    output = rest[0] if rest else ""
    emit(api_surface_markdown(target), output, target.rsplit(".", 1)[-1], "module")
elif kind == "directory":
    output, *exclude = rest or [""]
    emit(
        directory_surface_markdown(target, exclude),
        output,
        Path(target).resolve().name,
        "directory",
    )
elif kind == "api":
    if target in ("frontend", "all"):
        subprocess.run(
            ("npm", "run", "--silent", "api:package"), cwd=FRONTEND_ROOT, check=True
        )
    packages = (
        workspace_packages()
        if target == "all"
        else []
        if target == "frontend"
        else [resolve_package(target)]
    )
    for name, directory in packages:
        emit(
            directory_surface_markdown(
                str(directory), rest, title=name, heading_base=directory
            ),
            "",
            name,
            "package",
        )
else:
    sys.exit(f"unknown command {kind!r}; expected module, directory, or api")
