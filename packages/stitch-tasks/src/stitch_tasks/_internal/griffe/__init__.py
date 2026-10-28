from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from griffe import Alias, AliasResolutionError, Attribute, Class, Function, Kind, load

if TYPE_CHECKING:
    from griffe import Object

__all__ = ["TOP_LEVEL_KINDS", "api_surface_markdown", "public_members", "signature_of"]

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


def _heading(lineno: int, obj: Object | Alias, level: int) -> str:
    return f"{'#' * level} {lineno}: `{signature_of(obj)}`"


def api_surface_markdown(module_name: str) -> str:
    module = load(module_name)
    lines = [f"# {module_name}", ""]
    for lineno, member in public_members(module, TOP_LEVEL_KINDS):
        lines.extend([_heading(lineno, member, 4), ""])
        if member.kind is Kind.CLASS:
            for method_lineno, method in public_members(member, (Kind.FUNCTION,)):
                lines.extend([_heading(method_lineno, method, 5), ""])
    return "\n".join(lines)
