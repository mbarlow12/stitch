from __future__ import annotations

from pathlib import Path

import pytest

from stitch_tasks._internal.workspace import resolve_package


def make_project(root: Path, name: str, build_backend: str = "") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\n{build_backend}', encoding="utf-8"
    )
    return root


def test_default_module_name_is_the_normalised_project_name(tmp_path: Path) -> None:
    root = make_project(tmp_path / "proj", "my-pkg")
    assert resolve_package(str(root)) == ("my-pkg", root / "src" / "my_pkg")


def test_dotted_module_name_becomes_a_nested_directory(tmp_path: Path) -> None:
    root = make_project(
        tmp_path / "api",
        "stitch-api",
        '[tool.uv.build-backend]\nmodule-name = "stitch.api"\n',
    )
    assert resolve_package(str(root)) == ("stitch-api", root / "src" / "stitch" / "api")


def test_module_root_is_honoured(tmp_path: Path) -> None:
    root = make_project(
        tmp_path / "flat",
        "flat-pkg",
        '[tool.uv.build-backend]\nmodule-root = ""\n',
    )
    assert resolve_package(str(root)) == ("flat-pkg", root / "flat_pkg")


def test_a_path_inside_a_project_resolves_to_the_project(tmp_path: Path) -> None:
    root = make_project(tmp_path / "proj", "my-pkg")
    nested = root / "src" / "my_pkg" / "sub"
    nested.mkdir(parents=True)
    assert resolve_package(str(nested)) == ("my-pkg", root / "src" / "my_pkg")


def test_several_modules_are_rejected(tmp_path: Path) -> None:
    root = make_project(
        tmp_path / "multi",
        "multi-pkg",
        '[tool.uv.build-backend]\nmodule-name = ["foo", "bar"]\n',
    )
    with pytest.raises(ValueError, match="several modules"):
        resolve_package(str(root))


def test_an_unknown_target_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a path inside a project"):
        resolve_package("no-such-package-anywhere")


def test_an_installed_package_resolves_by_name() -> None:
    name, directory = resolve_package("stitch-tasks")
    assert name == "stitch-tasks"
    assert directory == Path(__file__).resolve().parents[1] / "src" / "stitch_tasks"
