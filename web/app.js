// sinfony playground: wiring between controls, pads, the Python engine, and audio.

import { Engine } from "./engine.js";
import { POINTS, PadView, mergePads, sameLayout } from "./pads.js";
import { Player, beatAtSeconds } from "./player.js";
import { drawRoll } from "./roll.js";
import { clampSeed, decodeHash, encodeHash, quantize } from "./share.js";
import { Synth } from "./synth.js";

const $ = (id) => document.getElementById(id);
const STYLE_SECTIONS = { tonal: ["A", "A'", "B", "A"], ambient: ["A", "B", "A'", "C", "A"] };
const MODES = {
  tonal: ["major", "minor"],
  ambient: ["dorian", "lydian", "aeolian", "pentatonic", "mixolydian", "phrygian", "major", "minor"],
};
const NOTE_NAMES = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];
const SLIDERS = ["tempo", "wiggle", "smooth", "density"];
const FORMAT = {
  tempo: (v) => `${Math.round(v)} bpm`,
  wiggle: (v) => v.toFixed(2),
  smooth: (v) => v.toFixed(1),
  density: (v) => v.toFixed(2),
};
const flat = (v) => Array(POINTS).fill(v);
const withMaterial = (s) => ({ ...s, material: s.material ?? s.label.replace(/'+$/, "") });

if (!window.AudioContext || !window.Worker) {
  document.body.innerHTML =
    '<p class="unsupported">Your browser can\'t run the playground: it needs Web Audio and Web Workers.</p>';
  throw new Error("unsupported browser");
}

const state = {
  params: { style: "tonal", seed: 0, key: null, tempo: null, wiggle: null, smooth: null, density: null },
  contour: {}, // material key -> 64 quantized points (drawn slots only)
  drawnContour: new Set(),
  tension: null, // flat quantized list, 64 per section, once the user draws tension
  sections: STYLE_SECTIONS.tonal.map((label) => withMaterial({ label })),
  piece: null,
};

// ---------- helpers
let toastTimer = null;
function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3500);
}

function readColors() {
  const css = getComputedStyle(document.documentElement);
  const v = (name) => css.getPropertyValue(name).trim();
  return {
    ink: v("--ink"), muted: v("--muted"), grid: v("--grid"), band: v("--band"), bandAlt: v("--band-alt"),
    accent: v("--accent"), playhead: v("--playhead"),
    voices: [v("--v1"), v("--v2"), v("--v3"), v("--v4"), v("--v5")],
  };
}
let colors = readColors();
const getColors = () => colors;
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  colors = readColors();
  redraw();
});

// ---------- pads
const contourPad = new PadView($("contour"), {
  linked: true,
  colors: getColors,
  onCommit: ({ values, touched }) => {
    for (const slot of touched) {
      state.contour[slot] = values[slot].map(quantize);
      state.drawnContour.add(slot);
    }
    requestCompose();
  },
});
const tensionPad = new PadView($("tension"), {
  linked: false,
  colors: getColors,
  onCommit: ({ values }) => {
    state.tension = state.sections.flatMap((_, i) => (values[String(i)] ?? flat(0.5)).map(quantize));
    requestCompose();
  },
});

function pieceMatchesSections() {
  return state.piece !== null && sameLayout(state.piece.sections, state.sections);
}

function refreshPads() {
  const contourDefaults = pieceMatchesSections()
    ? state.piece.pads.contour
    : Object.fromEntries(state.sections.map((s) => [s.material, flat(0.5)]));
  contourPad.setModel(state.sections, mergePads(contourDefaults, state.contour, state.drawnContour), state.drawnContour);
  const source = state.tension ?? (pieceMatchesSections() ? state.piece.pads.tension : null);
  const tension = Object.fromEntries(
    state.sections.map((_, i) => [String(i), source ? source.slice(i * POINTS, (i + 1) * POINTS) : flat(0.5)]),
  );
  tensionPad.setModel(state.sections, tension, state.tension ? state.sections.map((_, i) => String(i)) : []);
}

function clearDrawings(reason) {
  const had = state.drawnContour.size > 0 || state.tension !== null;
  state.contour = {};
  state.drawnContour = new Set();
  state.tension = null;
  if (had && reason) toast(reason);
}

// ---------- controls
function fillSelect(select, items) {
  select.replaceChildren(...items.map(([value, text]) => new Option(text, value)));
}
fillSelect($("root"), NOTE_NAMES.map((n, i) => [String(i), n]));
function fillModes(style) {
  fillSelect($("mode"), MODES[style].map((m) => [m, m[0].toUpperCase() + m.slice(1)]));
}
fillModes("tonal");

function syncControls(params) {
  $("seed").value = params.seed;
  $("style").value = params.style;
  fillModes(params.style);
  const [pc, mode] = params.key.split("-");
  $("root").value = pc;
  $("mode").value = mode;
  for (const name of SLIDERS) {
    $(name).value = params[name];
    $(`${name}-out`).textContent = FORMAT[name](Number(params[name]));
  }
}

function setSeed(seed) {
  state.params.seed = seed;
  state.params.key = null;
  state.params.tempo = null;
  requestCompose();
}

$("style").addEventListener("change", (e) => {
  const style = e.target.value;
  state.params = { style, seed: state.params.seed, key: null, tempo: null, wiggle: null, smooth: null, density: null };
  const next = STYLE_SECTIONS[style].map((label) => withMaterial({ label }));
  if (!sameLayout(next, state.sections)) clearDrawings("Drawing cleared: this style has different sections");
  state.sections = next;
  fillModes(style);
  refreshPads();
  requestCompose();
});
$("seed").addEventListener("change", (e) => {
  const seed = clampSeed(Number(e.target.value));
  e.target.value = seed;
  setSeed(seed);
});
$("dice").addEventListener("click", () => {
  const seed = Math.floor(Math.random() * 100000);
  $("seed").value = seed;
  setSeed(seed);
});
for (const id of ["root", "mode"]) {
  $(id).addEventListener("change", () => {
    state.params.key = `${$("root").value}-${$("mode").value}`;
    requestCompose();
  });
}
for (const name of SLIDERS) {
  $(name).addEventListener("input", (e) => {
    const v = Number(e.target.value);
    state.params[name] = v;
    $(`${name}-out`).textContent = FORMAT[name](v);
    requestCompose(300);
  });
}
$("loop").addEventListener("change", (e) => {
  if (player) player.loop = e.target.checked;
});
$("reset").addEventListener("click", () => {
  clearDrawings();
  refreshPads();
  requestCompose();
});
$("share").addEventListener("click", async () => {
  updateHash();
  try {
    await navigator.clipboard.writeText(location.href);
    toast("Link copied");
  } catch {
    toast("Copy the link from the address bar");
  }
});
$("midi").addEventListener("click", async () => {
  try {
    const b64 = await engine.midi(composeParams());
    const bytes = Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "audio/midi" }));
    const link = Object.assign(document.createElement("a"), {
      href: url,
      download: `sinfony-${state.params.style}-${state.params.seed}.mid`,
    });
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (err) {
    toast(err.message);
  }
});

// ---------- audio (created on the first user gesture, as browsers require)
let audio = null;
let player = null;
function ensureAudio() {
  if (!audio) {
    audio = new AudioContext();
    player = new Player(audio, new Synth(audio), { onEnd: setPlayingUI });
    player.loop = $("loop").checked;
    if (state.piece) player.load(state.piece);
  }
  if (audio.state === "suspended") audio.resume();
}
function setPlayingUI() {
  $("play").textContent = player?.playing ? "■ Stop" : "▶ Play";
  redraw();
}
$("play").addEventListener("click", () => {
  ensureAudio();
  if (player.playing) player.stop();
  else player.play();
  setPlayingUI();
});

// ---------- engine
let engine = null;
function startEngine() {
  $("loading").hidden = false;
  $("error").hidden = true;
  const worker = new Worker("worker.js", { type: "module" });
  worker.onerror = (e) => showError(e.message || "the engine worker failed to start");
  engine = new Engine(worker, {
    onProgress: ({ progress, stage }) => {
      $("loading-bar").value = progress;
      $("loading-stage").textContent = progress >= 1 ? "Ready" : `${stage}…`;
      if (progress >= 1) $("loading").hidden = true;
    },
  });
}
function showError(message) {
  $("loading").hidden = true;
  $("error-text").textContent = message;
  $("error").hidden = false;
}
$("retry").addEventListener("click", () => {
  engine.worker.terminate();
  startEngine();
  requestCompose();
});

function composeParams() {
  const p = { style: state.params.style, seed: state.params.seed };
  for (const name of ["key", ...SLIDERS]) if (state.params[name] !== null) p[name] = state.params[name];
  if (state.drawnContour.size) {
    p.contour = Object.fromEntries([...state.drawnContour].map((k) => [k, state.contour[k]]));
  }
  if (state.tension) p.tension = state.tension;
  return p;
}

let debounce = null;
function requestCompose(delay = 0) {
  clearTimeout(debounce);
  debounce = setTimeout(runCompose, delay);
}

async function runCompose() {
  $("status").textContent = "composing…";
  try {
    const piece = await engine.compose(composeParams());
    if (piece) applyPiece(piece);
  } catch (err) {
    if (err.kind === "load") return showError(err.message);
    if (err.kind === "value" && /tension/.test(err.message) && state.tension) {
      state.tension = null;
      toast(`Tension drawing ignored: ${err.message}`);
      refreshPads();
      return runCompose();
    }
    if (err.kind === "value" && /contour/.test(err.message) && state.drawnContour.size) {
      clearDrawings(`Contour drawing ignored: ${err.message}`);
      refreshPads();
      return runCompose();
    }
    if (err.kind === "value" && /key|mode/.test(err.message) && state.params.key) {
      state.params.key = null;
      toast(`Key ignored: ${err.message}`);
      return runCompose();
    }
    toast(err.kind === "value" ? err.message : "Something went wrong composing");
    console.error(err);
    $("status").textContent = "";
  }
}

function applyPiece(piece) {
  if (!sameLayout(piece.sections, state.sections)) clearDrawings("Drawing cleared: the piece has different sections");
  state.sections = piece.sections.map(withMaterial);
  state.piece = piece;
  refreshPads();
  syncControls(piece.params);
  updateHash();
  if (player) player.load(piece);
  $("play").disabled = false;
  const [pc, mode] = piece.params.key.split("-");
  $("status").textContent =
    `${NOTE_NAMES[Number(pc)]} ${mode} · ${Math.round(piece.params.tempo)} bpm · ${Math.round(piece.duration_s)} s`;
  redraw();
}

// ---------- share links
function updateHash() {
  const p = composeParams();
  const hash = encodeHash({
    style: p.style, seed: p.seed, key: p.key ?? null, tempo: p.tempo ?? null, wiggle: p.wiggle ?? null,
    smooth: p.smooth ?? null, density: p.density ?? null, contour: p.contour ?? {}, tension: p.tension ?? null,
  });
  history.replaceState(null, "", hash);
}

function loadFromHash() {
  const { state: s, ignored } = decodeHash(location.hash);
  state.params = { style: s.style, seed: s.seed, key: s.key, tempo: s.tempo, wiggle: s.wiggle, smooth: s.smooth, density: s.density };
  state.contour = s.contour;
  state.drawnContour = new Set(Object.keys(s.contour));
  state.tension = s.tension;
  state.sections = STYLE_SECTIONS[s.style].map((label) => withMaterial({ label }));
  $("style").value = s.style;
  $("seed").value = s.seed;
  fillModes(s.style);
  if (ignored.length) toast(`Ignored invalid link fields: ${ignored.join(", ")}`);
}
window.addEventListener("hashchange", () => {
  loadFromHash();
  refreshPads();
  requestCompose();
});

// ---------- drawing loop
function redraw() {
  const pos = player && player.playing ? player.position : null;
  drawRoll($("roll"), state.piece, pos, getColors);
  const u = pos !== null && state.piece
    ? Math.min(1, Math.max(0, beatAtSeconds(state.piece.beat_s, pos) / state.piece.total_beats))
    : null;
  contourPad.draw(u);
  tensionPad.draw(u);
}
function frame() {
  if (player && player.playing) redraw();
  requestAnimationFrame(frame);
}
new ResizeObserver(() => redraw()).observe($("roll"));

window.__sinfony = {
  get piece() {
    return state.piece;
  },
  state,
  compose: runCompose,
};

loadFromHash();
refreshPads();
startEngine();
requestCompose();
requestAnimationFrame(frame);
