from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from griffe import Alias, AliasResolutionError, Attribute, Class, Function, Kind, load

from ._target import resolve_target

if TYPE_CHECKING:
    from griffe import Object

__all__ = [
    "TOP_LEVEL_KINDS",
    "api_surface_markdown",
    "directory_surface_markdown",
    "public_members",
    "resolve_target",
    "signature_of",
]

TOP_LEVEL_KINDS = (Kind.FUNCTION, Kind.CLASS, Kind.ATTRIBUTE)


def public_members(
    parent: Object | Alias, kinds: tuple[Kind, ...]
) -> Iterator[tuple[int, Object | Alias]]:
    found: list[tuple[int, Object | Alias]] = []
    for member in parent.members.values():
        if not member.is_public or member.kind not in kinds:
            continue
        try:
            lineno = member.lineno
        except AliasResolutionError:
            continue
        if lineno is None:
            continue
        found.append((lineno, member))
    yield from sorted(found, key=lambda pair: pair[0])


def signature_of(obj: Object | Alias) -> str:
    target = obj.final_target if isinstance(obj, Alias) else obj
    if isinstance(target, Class):
        bases = ", ".join(str(base) for base in target.bases)
        return f"class {target.name}({bases})" if bases else f"class {target.name}"
    if isinstance(target, Function):
        return target.signature(return_type=True)
    if isinstance(target, Attribute):
        if target.annotation is not None:
            return f"{target.name}: {target.annotation}"
        if target.value is not None:
            return f"{target.name} = {target.value}"
    return target.name


def _entry(lineno: int, obj: Object | Alias, prefix: str = "") -> str:
    return f"**{lineno}: `{prefix}{signature_of(obj)}`**"


def _member_lines(module: Object | Alias) -> list[str]:
    lines: list[str] = []
    for lineno, member in public_members(module, TOP_LEVEL_KINDS):
        lines.extend([_entry(lineno, member), ""])
        if member.kind is Kind.CLASS:
            for method_lineno, method in public_members(member, (Kind.FUNCTION,)):
                lines.extend([_entry(method_lineno, method, f"{member.name}."), ""])
    return lines


def api_surface_markdown(module_name: str) -> str:
    module = load(module_name)
    return "\n".join([f"# {module_name}", "", *_member_lines(module)])


def _module_paths(directory: Path) -> Iterator[Path]:
    for path in sorted(directory.rglob("*.py")):
        parts = path.relative_to(directory).parts
        if any(part.startswith(".") or part == "__pycache__" for part in parts):
            continue
        yield path


def _package_root(path: Path, fallback: Path) -> Path:
    for parent in path.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return fallback


def directory_surface_markdown(directory: str) -> str:
    root = Path(directory).resolve()
    lines = [f"# {root.name}", ""]
    for path in _module_paths(root):
        name, search_paths = resolve_target(str(path))
        heading = path.relative_to(_package_root(path, root)).as_posix()
        lines.extend([f"## {heading}", ""])
        lines.extend(_member_lines(load(name, search_paths=search_paths)))
    return "\n".join(lines)
