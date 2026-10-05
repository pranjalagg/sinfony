// Share links: the whole drawing and settings live in the URL hash.

export const POINTS = 64;
const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
const STYLES = ["tonal", "ambient"];
const RANGES = { tempo: [40, 200], wiggle: [0, 1], smooth: [0, 5], density: [0, 1] };

const clamp01 = (v) => Math.min(1, Math.max(0, v));
const fmt = (x) => String(Math.round(x * 1000) / 1000);

/** Round a value to one of the 64 levels a link can store. */
export function quantize(v) {
  return Math.round(clamp01(v) * 63) / 63;
}

export function encodePoints(points) {
  return points.map((v) => ALPHABET[Math.round(clamp01(v) * 63)]).join("");
}

export function decodePoints(text, expected) {
  if (expected !== undefined && text.length !== expected) {
    throw new Error(`expected ${expected} points, got ${text.length}`);
  }
  return [...text].map((ch) => {
    const i = ALPHABET.indexOf(ch);
    if (i < 0) throw new Error(`bad point character ${JSON.stringify(ch)}`);
    return i / 63;
  });
}

export function encodeHash(state) {
  const parts = ["v=1", `style=${state.style}`, `seed=${state.seed}`];
  if (state.key) parts.push(`key=${state.key}`);
  for (const name of Object.keys(RANGES)) {
    if (state[name] !== null && state[name] !== undefined) parts.push(`${name}=${fmt(state[name])}`);
  }
  const contour = Object.entries(state.contour || {});
  if (contour.length) {
    parts.push("c=" + contour.map(([k, pts]) => `${encodeURIComponent(k)}.${encodePoints(pts)}`).join("~"));
  }
  if (state.tension) parts.push(`t=${encodePoints(state.tension)}`);
  return "#" + parts.join("&");
}

export function decodeHash(hash) {
  const state = {
    style: "tonal", seed: 0, key: null, tempo: null, wiggle: null, smooth: null, density: null,
    contour: {}, tension: null,
  };
  const ignored = [];
  const q = new URLSearchParams(String(hash || "").replace(/^#/, ""));

  if (q.has("style")) {
    const s = q.get("style");
    if (STYLES.includes(s)) state.style = s;
    else ignored.push("style");
  }
  if (q.has("seed")) {
    const raw = q.get("seed");
    const n = Number(raw);
    if (raw !== "" && Number.isInteger(n) && n >= 0 && n < 2 ** 31) state.seed = n;
    else ignored.push("seed");
  }
  if (q.has("key")) {
    const m = /^(\d{1,2})-([a-z]+)$/.exec(q.get("key"));
    if (m && Number(m[1]) <= 11) state.key = q.get("key");
    else ignored.push("key");
  }
  for (const [name, [lo, hi]] of Object.entries(RANGES)) {
    if (!q.has(name)) continue;
    const raw = q.get(name);
    const n = Number(raw);
    if (raw !== "" && Number.isFinite(n) && n >= lo && n <= hi) state[name] = n;
    else ignored.push(name);
  }
  if (q.has("c")) {
    try {
      for (const entry of q.get("c").split("~")) {
        const dot = entry.indexOf(".");
        if (dot < 1) throw new Error("missing section key");
        state.contour[decodeURIComponent(entry.slice(0, dot))] = decodePoints(entry.slice(dot + 1), POINTS);
      }
    } catch {
      state.contour = {};
      ignored.push("c");
    }
  }
  if (q.has("t")) {
    try {
      const pts = decodePoints(q.get("t"));
      if (!pts.length || pts.length % POINTS) throw new Error("tension length");
      state.tension = pts;
    } catch {
      ignored.push("t");
    }
  }
  return { state, ignored };
}
