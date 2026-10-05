import assert from "node:assert/strict";
import test from "node:test";

import { POINTS, decodeHash, decodePoints, encodeHash, encodePoints, quantize } from "../share.js";

const ramp = Array.from({ length: POINTS }, (_, i) => i / (POINTS - 1));

test("points round-trip within quantization", () => {
  const back = decodePoints(encodePoints(ramp));
  back.forEach((v, i) => assert.ok(Math.abs(v - ramp[i]) <= 0.5 / 63 + 1e-12));
  assert.deepEqual(decodePoints(encodePoints(back)), back);
});

test("quantize is idempotent and clamps", () => {
  assert.equal(quantize(quantize(0.37)), quantize(0.37));
  assert.equal(quantize(2), 1);
  assert.equal(quantize(-1), 0);
});

test("decodePoints rejects bad input", () => {
  assert.throws(() => decodePoints("@@@"));
  assert.throws(() => decodePoints("AAA", POINTS));
});

test("hash round-trips a full state", () => {
  const state = {
    style: "ambient", seed: 42, key: "2-dorian", tempo: 60, wiggle: 0.3, smooth: 1.5, density: 0.4,
    contour: { A: ramp.map(quantize), "A@3": ramp.map((v) => quantize(1 - v)) },
    tension: [...ramp, ...ramp].map(quantize),
  };
  const { state: back, ignored } = decodeHash(encodeHash(state));
  assert.deepEqual(ignored, []);
  assert.deepEqual(back, state);
});

test("hash omits unset fields", () => {
  const h = encodeHash({
    style: "tonal", seed: 1, key: null, tempo: null, wiggle: null, smooth: null, density: null,
    contour: {}, tension: null,
  });
  assert.equal(h, "#v=1&style=tonal&seed=1");
});

test("malformed fields fall back to defaults and are reported", () => {
  const { state, ignored } = decodeHash("#v=1&style=jazz&seed=-4&key=13-major&tempo=999&c=A.@@@&t=xyz");
  assert.equal(state.style, "tonal");
  assert.equal(state.seed, 0);
  assert.equal(state.key, null);
  assert.equal(state.tempo, null);
  assert.deepEqual(state.contour, {});
  assert.equal(state.tension, null);
  assert.deepEqual([...ignored].sort(), ["c", "key", "seed", "style", "t", "tempo"]);
});

test("empty hash gives defaults", () => {
  const { state, ignored } = decodeHash("");
  assert.equal(state.style, "tonal");
  assert.equal(state.seed, 0);
  assert.deepEqual(ignored, []);
});

test("clampSeed keeps seeds in the engine's range", async () => {
  const { clampSeed, SEED_MAX } = await import("../share.js");
  assert.equal(clampSeed(3000000000), SEED_MAX);
  assert.equal(clampSeed(-5), 0);
  assert.equal(clampSeed(12.7), 12);
  assert.equal(clampSeed(Number.NaN), 0);
  assert.equal(SEED_MAX, 2 ** 31 - 1);
});
