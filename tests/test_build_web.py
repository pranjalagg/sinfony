import importlib.util
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_script():
    spec = importlib.util.spec_from_file_location("build_web", ROOT / "scripts" / "build_web.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_writes_wheel_and_manifest(tmp_path):
    out = tmp_path / "wheels"
    (out).mkdir()
    (out / "sinfony-0.0.1-py3-none-any.whl").write_bytes(b"old")
    wheel = load_script().build(out)
    assert wheel.parent == out and wheel.name.startswith("sinfony-")
    assert json.loads((out / "manifest.json").read_text()) == {"sinfony": wheel.name}
    assert not (out / "sinfony-0.0.1-py3-none-any.whl").exists()
    names = zipfile.ZipFile(wheel).namelist()
    assert "sinfony/web.py" in names
    assert not any(n.startswith("tests/") for n in names)
