"""Build the interface and the sqlite store before the Vercel function is packed.

The Docker image does this inside the image. This script is the same two steps
for the Vercel build, which runs on the machine invoking `vercel deploy`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_interface() -> None:
    frontend = ROOT / "frontend"
    subprocess.check_call(["npm", "ci"], cwd=frontend)
    subprocess.check_call(["npm", "run", "build"], cwd=frontend)
    public = ROOT / "public"
    staging = ROOT / ".public-build"
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(frontend / "dist", staging)
    if public.exists():
        shutil.rmtree(public)
    staging.rename(public)


def build_store() -> None:
    sys.path.insert(0, str(ROOT / "backend"))
    os.environ["DAYMARK_ROOT"] = str(ROOT)
    from daymark.build import main

    main()


if __name__ == "__main__":
    build_interface()
    build_store()
