/* Pyodide worker: runs sinfony.web in the browser. Module worker: Pyodide 314 has no classic-worker support. */

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

const progress = (value, stage) => self.postMessage({ progress: value, stage });

const PY_BRIDGE = `
import base64, json
import sinfony.web as web

def _call(op, params_json):
    try:
        params = json.loads(params_json)
        if op == "compose":
            result = web.compose(params)
        elif op == "midi":
            result = base64.b64encode(web.midi(params)).decode("ascii")
        else:
            raise ValueError(f"unknown operation {op!r}")
        return json.dumps({"ok": True, "result": result})
    except ValueError as e:
        return json.dumps({"ok": False, "kind": "value", "error": str(e)})
    except Exception as e:
        return json.dumps({"ok": False, "kind": "internal", "error": f"{type(e).__name__}: {e}"})
`;

const ready = (async () => {
  progress(0.05, "Loading Python");
  const py = await loadPyodide({ indexURL: PYODIDE_URL });
  progress(0.45, "Loading numpy");
  await py.loadPackage(["numpy", "micropip"]);
  progress(0.7, "Installing sinfony");
  const manifest = await (await fetch("wheels/manifest.json")).json();
  const micropip = py.pyimport("micropip");
  await micropip.install("mido");
  const wheelUrl = new URL(`wheels/${manifest.sinfony}`, self.location.href).href;
  await micropip.install.callKwargs(wheelUrl, { deps: false });
  progress(0.9, "Warming up");
  py.runPython(PY_BRIDGE);
  progress(1, "Ready");
  return py.globals.get("_call");
})();

self.onmessage = async (event) => {
  const { id, op, params } = event.data;
  try {
    const call = await ready;
    const reply = JSON.parse(call(op, JSON.stringify(params)));
    self.postMessage({ id, ...reply });
  } catch (err) {
    self.postMessage({ id, ok: false, kind: "load", error: String((err && err.message) || err) });
  }
};
