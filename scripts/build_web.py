"""Build the playground's Python payload: the sinfony wheel + a manifest in web/wheels/."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(out: Path = ROOT / "web" / "wheels") -> Path:
    dist = ROOT / "dist"
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(dist)], cwd=ROOT, check=True)
    wheels = sorted(dist.glob("sinfony-*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        raise SystemExit("uv build produced no sinfony wheel")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("sinfony-*.whl"):
        old.unlink()
    wheel = Path(shutil.copy2(wheels[-1], out))
    (out / "manifest.json").write_text(json.dumps({"sinfony": wheel.name}))
    return wheel


if __name__ == "__main__":
    print(f"built {build()}")
