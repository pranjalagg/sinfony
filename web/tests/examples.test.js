import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { exampleHash, loadExamples } from "../examples.js";
import { decodeHash } from "../share.js";

const examples = JSON.parse(readFileSync(new URL("../examples.json", import.meta.url), "utf8"));
const MATERIALS = { tonal: ["A", "B"], ambient: ["A", "B", "C"] };
const SECTIONS = { tonal: 4, ambient: 5 };
const POINTS = 64;

test("exampleHash round-trips every example", () => {
  for (const ex of examples) {
    const { state, ignored } = decodeHash(exampleHash(ex));
    assert.deepEqual(ignored, [], ex.id);
    const p = ex.params;
    assert.equal(state.style, p.style);
    assert.equal(state.seed, p.seed);
    for (const name of ["key", "wiggle", "smooth", "density", "tempo"]) {
      assert.equal(state[name], p[name] ?? null, `${ex.id} ${name}`);
    }
    assert.deepEqual(Object.keys(state.contour), Object.keys(p.contour ?? {}), ex.id);
    for (const [k, pts] of Object.entries(p.contour ?? {})) {
      pts.forEach((v, i) => assert.ok(Math.abs(state.contour[k][i] - v) < 1e-9, `${ex.id} contour ${k}`));
    }
    assert.equal(state.tension?.length ?? null, p.tension?.length ?? null, ex.id);
  }
});

test("example contour keys match the style's materials", () => {
  for (const ex of examples) {
    const { style, contour = {}, tension } = ex.params;
    for (const key of Object.keys(contour)) assert.ok(MATERIALS[style].includes(key), `${ex.id} ${key}`);
    if (tension) assert.equal(tension.length, POINTS * SECTIONS[style], ex.id);
  }
});

test("loadExamples returns [] on failure", async () => {
  assert.deepEqual(await loadExamples(() => Promise.reject(new Error("offline"))), []);
  assert.deepEqual(await loadExamples(async () => ({ ok: false })), []);
  assert.deepEqual(await loadExamples(async () => ({ ok: true, json: async () => ({}) })), []);
  assert.deepEqual(await loadExamples(async () => ({ ok: true, json: async () => [{ id: 1 }] })), []);
});

test("loadExamples returns the list", async () => {
  const got = await loadExamples(async () => ({ ok: true, json: async () => examples }));
  assert.deepEqual(got, examples);
});
