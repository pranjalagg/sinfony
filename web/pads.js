// Drawing pads: pure geometry (tested in Node) plus a small canvas view.

import { fitCanvas } from "./canvas.js";

export const POINTS = 64;

/** Place sections across [0, 1]: by beats when known, else equal widths. */
export function layoutSections(sections) {
  const spans = sections.map((s) => (s.end !== undefined ? s.end - s.start : 1));
  const total = spans.reduce((a, b) => a + b, 0);
  let u = 0;
  return sections.map((s, i) => {
    const u0 = u;
    u += spans[i] / total;
    return {
      label: s.label,
      material: s.material ?? s.label.replace(/'+$/, ""),
      u0,
      u1: i === sections.length - 1 ? 1 : u,
    };
  });
}

/** Horizontal position (0..1) of point k of a section: evenly spaced cell centres. */
export function pointU(sec, k) {
  return sec.u0 + ((k + 0.5) / POINTS) * (sec.u1 - sec.u0);
}

/** Pointer samples -> stroke sorted by u, y clamped (later samples win at equal u). */
export function cleanStroke(samples) {
  const byU = new Map();
  for (const p of samples) byU.set(Math.round(p.u * 1e4), { u: p.u, y: Math.min(1, Math.max(0, p.y)) });
  return [...byU.values()].sort((a, b) => a.u - b.u);
}

/** Height of the stroke at u (linear between samples), or null outside it. */
export function strokeAt(stroke, u) {
  if (!stroke.length || u < stroke[0].u || u > stroke[stroke.length - 1].u) return null;
  let i = 1;
  while (i < stroke.length && stroke[i].u < u) i++;
  if (i >= stroke.length) return stroke[stroke.length - 1].y;
  const a = stroke[i - 1];
  const b = stroke[i];
  if (b.u === a.u) return b.y;
  return a.y + ((u - a.u) / (b.u - a.u)) * (b.y - a.y);
}

/** 3-point moving average over lo..hi, keeping lo and hi unchanged. */
export function smoothRange(points, lo, hi) {
  const out = points.slice();
  for (let k = lo + 1; k < hi; k++) out[k] = (points[k - 1] + points[k] + points[k + 1]) / 3;
  return out;
}

const slotOf = (sec, i, linked) => (linked ? sec.material : String(i));

/** Apply a stroke; returns new arrays for touched slots and the set of touched slot keys. */
export function applyStroke(values, sections, stroke, linked) {
  const next = { ...values };
  const touched = new Set();
  sections.forEach((sec, i) => {
    const slot = slotOf(sec, i, linked);
    const pts = (next[slot] ?? Array(POINTS).fill(0.5)).slice();
    let lo = Infinity;
    let hi = -Infinity;
    for (let k = 0; k < POINTS; k++) {
      const y = strokeAt(stroke, pointU(sec, k));
      if (y !== null) {
        pts[k] = y;
        lo = Math.min(lo, k);
        hi = Math.max(hi, k);
      }
    }
    if (hi >= lo) {
      next[slot] = smoothRange(pts, lo, hi);
      touched.add(slot);
    }
  });
  return { values: next, touched };
}

/** Drawn slots keep the user's points; everything else comes from the defaults. */
export function mergePads(defaults, values, drawn) {
  const out = {};
  for (const [slot, pts] of Object.entries(defaults)) {
    out[slot] = drawn.has(slot) && values[slot] ? values[slot] : pts;
  }
  return out;
}

/** True when both section lists have the same materials in the same order. */
export function sameLayout(a, b) {
  return a.length === b.length && a.every((s, i) => s.material === b[i].material);
}

export class PadView {
  constructor(canvas, { linked, colors, onCommit }) {
    this.canvas = canvas;
    this.linked = linked;
    this.colors = colors;
    this.onCommit = onCommit;
    this.sections = [];
    this.values = {};
    this.drawn = new Set();
    this.samples = null;
    this.preview = null;
    canvas.addEventListener("pointerdown", (e) => this._down(e));
    canvas.addEventListener("pointermove", (e) => this._move(e));
    canvas.addEventListener("pointerup", (e) => this._up(e));
    canvas.addEventListener("pointercancel", () => this._cancel());
    new ResizeObserver(() => this.draw()).observe(canvas);
  }

  setModel(sections, values, drawnSlots) {
    this.sections = layoutSections(sections);
    this.values = values;
    this.drawn = new Set(drawnSlots);
    this.draw();
  }

  _uv(e) {
    const r = this.canvas.getBoundingClientRect();
    return { u: (e.clientX - r.left) / r.width, y: 1 - (e.clientY - r.top) / r.height };
  }

  _down(e) {
    if (!this.sections.length) return;
    try {
      this.canvas.setPointerCapture(e.pointerId);
    } catch {
      /* synthetic or already-released pointers can't be captured; drawing still works */
    }
    this.samples = [this._uv(e)];
  }

  _move(e) {
    if (!this.samples) return;
    this.samples.push(this._uv(e));
    this.preview = applyStroke(this.values, this.sections, cleanStroke(this.samples), this.linked).values;
    this.draw();
  }

  _up(e) {
    if (!this.samples) return;
    this.samples.push(this._uv(e));
    const { values, touched } = applyStroke(this.values, this.sections, cleanStroke(this.samples), this.linked);
    this.samples = null;
    this.preview = null;
    if (!touched.size) return this.draw();
    this.values = values;
    touched.forEach((slot) => this.drawn.add(slot));
    this.draw();
    this.onCommit({ values, touched });
  }

  _cancel() {
    this.samples = null;
    this.preview = null;
    this.draw();
  }

  draw(playheadU = null) {
    const ctx = fitCanvas(this.canvas);
    const W = this.canvas.clientWidth;
    const H = this.canvas.clientHeight;
    const c = this.colors();
    ctx.clearRect(0, 0, W, H);
    const values = this.preview ?? this.values;
    const counts = {};
    for (const s of this.sections) counts[s.material] = (counts[s.material] || 0) + 1;

    this.sections.forEach((sec, i) => {
      const x0 = sec.u0 * W;
      const x1 = sec.u1 * W;
      ctx.fillStyle = i % 2 ? c.band : c.bandAlt;
      ctx.fillRect(x0, 0, x1 - x0, H);
      if (this.linked && counts[sec.material] > 1) {
        ctx.globalAlpha = 0.07; // linked sections share an accent tint
        ctx.fillStyle = c.accent;
        ctx.fillRect(x0, 0, x1 - x0, H);
        ctx.globalAlpha = 1;
      }
      ctx.fillStyle = c.muted;
      ctx.font = "600 12px system-ui, sans-serif";
      const linkedMark = this.linked && counts[sec.material] > 1 ? " ⛓" : "";
      ctx.fillText(sec.label + linkedMark, x0 + 8, 16);
      if (i) {
        ctx.strokeStyle = c.grid;
        ctx.beginPath();
        ctx.moveTo(x0, 0);
        ctx.lineTo(x0, H);
        ctx.stroke();
      }
    });

    this.sections.forEach((sec, i) => {
      const slot = slotOf(sec, i, this.linked);
      const pts = values[slot];
      if (!pts) return;
      const drawn = this.drawn.has(slot) || (this.preview && this.preview[slot] !== this.values[slot]);
      ctx.strokeStyle = drawn ? c.accent : c.muted;
      ctx.lineWidth = drawn ? 2.5 : 1.5;
      ctx.setLineDash(drawn ? [] : [5, 4]);
      ctx.beginPath();
      pts.forEach((v, k) => {
        const x = pointU(sec, k) * W;
        const y = (1 - v) * (H - 24) + 20;
        if (k) ctx.lineTo(x, y);
        else ctx.moveTo(x, y);
      });
      ctx.stroke();
    });
    ctx.setLineDash([]);

    if (playheadU !== null) {
      ctx.strokeStyle = c.playhead;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(playheadU * W, 0);
      ctx.lineTo(playheadU * W, H);
      ctx.stroke();
    }
  }
}
