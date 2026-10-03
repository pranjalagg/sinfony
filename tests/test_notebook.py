import json
from pathlib import Path

NOTEBOOK = Path(__file__).parent.parent / "notebooks" / "01_tour.ipynb"


def test_tour_notebook_runs(monkeypatch):
    monkeypatch.setattr("sinfony.render.play.play", lambda audio, sr=44100: None)
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    code = [c for c in cells if c["cell_type"] == "code"]
    assert len(code) >= 8
    namespace: dict = {}
    for cell in code:
        exec("".join(cell["source"]), namespace)
