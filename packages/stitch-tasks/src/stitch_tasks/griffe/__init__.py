from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from griffe import AliasResolutionError, Kind, load

if TYPE_CHECKING:
    from griffe import Object

__all__ = ["TOP_LEVEL_KINDS", "api_surface_markdown", "public_members", "signature_of"]

TOP_LEVEL_KINDS = (Kind.FUNCTION, Kind.CLASS, Kind.ATTRIBUTE)


def public_members(parent: Object, kinds: tuple[Kind, ...]) -> Iterator[Object]:
    members = []
    for member in parent.members.values():
        if not member.is_public or member.kind not in kinds:
            continue
        try:
            lineno = member.lineno
        except AliasResolutionError:
            continue
        if lineno is None:
            continue
        members.append((lineno, member))
    for _, member in sorted(members, key=lambda pair: pair[0]):
        yield member


def signature_of(obj: Object) -> str:
    if obj.kind is Kind.CLASS:
        bases = ", ".join(str(base) for base in obj.bases)
        return f"class {obj.name}({bases})" if bases else f"class {obj.name}"
    if obj.kind is Kind.FUNCTION:
        returns = f" -> {obj.returns}" if obj.returns else ""
        return f"{obj.signature()}{returns}"
    return f"{obj.name}: {obj.annotation}" if obj.annotation else obj.name


def _heading(obj: Object, level: int) -> str:
    return f"{'#' * level} {obj.lineno}: `{signature_of(obj)}`"


def api_surface_markdown(module_name: str) -> str:
    module = load(module_name)
    lines = [f"# {module_name}", ""]
    for member in public_members(module, TOP_LEVEL_KINDS):
        lines.extend([_heading(member, 4), ""])
        if member.kind is Kind.CLASS:
            for method in public_members(member, (Kind.FUNCTION,)):
                lines.extend([_heading(method, 5), ""])
    return "\n".join(lines)
