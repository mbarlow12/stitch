from __future__ import annotations

from pathlib import Path

import pytest

from stitch_tasks._internal.griffe import directory_surface_markdown

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def surface() -> str:
    return directory_surface_markdown(str(FIXTURES / "treeproj"))


def test_matches_the_expected_markdown(surface: str) -> None:
    assert surface == (FIXTURES / "treeproj.md").read_text(encoding="utf-8")


def test_cache_directories_are_skipped(tmp_path: Path) -> None:
    cached = tmp_path / "__pycache__"
    cached.mkdir()
    (cached / "stale.py").write_text("def ghost() -> None: ...\n", encoding="utf-8")
    assert "ghost" not in directory_surface_markdown(str(tmp_path))
