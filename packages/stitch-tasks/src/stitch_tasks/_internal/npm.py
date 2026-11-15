from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["FRONTEND_PACKAGE", "frontend_api_surface"]

FRONTEND_PACKAGE = "stitch-frontend"
FRONTEND_ROOT = Path("deployments") / FRONTEND_PACKAGE


def frontend_api_surface() -> None:
    subprocess.run(
        ("npm", "run", "--silent", "api:package"), cwd=FRONTEND_ROOT, check=True
    )
