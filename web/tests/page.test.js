import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(new URL("../style.css", import.meta.url), "utf8");
const rule = (selector) => {
  const m = new RegExp(`(?:^|\\n)${selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\{([^}]*)\\}`).exec(css);
  assert.ok(m, `no rule for ${selector}`);
  return m[1];
};

const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");

const IDS = [
  "play", "seed", "dice", "style", "root", "mode", "tempo", "tempo-out", "wiggle", "wiggle-out", "smooth",
  "smooth-out", "density", "density-out", "loop", "share", "midi", "reset", "loading", "loading-stage",
  "loading-bar", "error", "error-text", "retry", "contour", "tension", "roll", "status", "toast",
];

/** The markup from a data-control/data-pad marker up to the next one. */
function block(kind, name) {
  const start = html.indexOf(`data-${kind}="${name}"`);
  assert.ok(start >= 0, `missing data-${kind}="${name}"`);
  const rest = html.slice(start + 1);
  const next = rest.search(/data-(control|pad)="/);
  return next < 0 ? rest : rest.slice(0, next);
}

test("keeps every existing id", () => {
  for (const id of IDS) assert.ok(html.includes(`id="${id}"`), id);
});

test("every control has a plain line", () => {
  for (const name of ["style", "key", "tempo", "smooth", "wiggle", "density", "seed", "loop", "share", "midi", "reset"]) {
    assert.ok(block("control", name).includes('class="hint"'), name);
  }
});

test("math controls have a closed disclosure", () => {
  for (const name of ["style", "key", "tempo", "smooth", "wiggle", "density", "seed"]) {
    const b = block("control", name);
    assert.match(b, /<details class="math">/, name);
    assert.doesNotMatch(b, /<details class="math" open/, name);
    assert.match(b, /<summary[^>]*aria-label="[^"]*math[^"]*"[^>]*>ⓘ<\/summary>/, name);
  }
});

test("pads explain themselves", () => {
  const contour = block("pad", "contour");
  const tension = block("pad", "tension");
  const roll = block("pad", "roll");
  assert.ok(contour.includes("Melody shape"));
  assert.ok(tension.includes("Tension"));
  assert.ok(roll.includes("What you'll hear") && roll.includes('id="legend"'));
  for (const b of [contour, tension]) {
    assert.ok(b.includes('class="hint"'));
    assert.match(b, /<details class="math">/);
  }
});

test("old titles are gone", () => {
  assert.ok(!html.includes("Melody contour"));
  assert.ok(!html.includes(">Result<"));
});

test("new ids exist", () => {
  for (const id of ["examples", "listen", "listen-text", "listen-close"]) assert.ok(html.includes(`id="${id}"`), id);
});

test("smoothness math says what Tonal copies do", () => {
  const b = block("control", "smooth");
  assert.ok(b.includes("fixed cost"), "mentions the fixed cost of copy joins");
  assert.ok(b.includes("motif"));
});

test("key math starts the stack of fifths at k = −1", () => {
  assert.ok(block("control", "key").includes("k = −1…5"));
});

test("opening a pad's math never squeezes its canvas away", () => {
  assert.doesNotMatch(rule(".stage"), /(^|\s)height:\s*100vh/);
  assert.match(rule(".stage"), /min-height:\s*100vh/);
  assert.doesNotMatch(rule(".pad"), /overflow:\s*hidden/);
  const floor = /min-height:\s*(\d+)px/.exec(rule(".pad canvas"));
  assert.ok(floor && Number(floor[1]) >= 100, "canvas keeps a usable height");
});

test("the panel's plain lines are one short line", () => {
  for (const name of ["style", "key", "tempo", "smooth", "wiggle", "density", "seed", "loop", "share", "midi", "reset"]) {
    const m = /<p class="hint">([^<]*)<\/p>/.exec(block("control", name));
    assert.ok(m, name);
    assert.ok(m[1].length <= 60, `${name} hint is ${m[1].length} characters`);
  }
});

test("the full explanation sits behind the info button", () => {
  for (const name of ["style", "key", "tempo", "smooth", "wiggle", "density", "seed"]) {
    assert.match(block("control", name), /<details class="math">[\s\S]*<p class="more">[\s\S]*<p class="formula">/, name);
  }
});

test("light is the default look; dark is opt-in", () => {
  assert.ok(html.includes('id="theme"'));
  assert.doesNotMatch(css, /prefers-color-scheme:\s*dark/);
  assert.match(css, /:root\[data-theme="dark"\]/);
});
