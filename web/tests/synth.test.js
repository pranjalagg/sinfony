import assert from "node:assert/strict";
import test from "node:test";

import { MAX_VOICES, impulseData, midiToHz, noteLevel, partialList, voiceToSteal } from "../synth.js";

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test("midiToHz is equal temperament", () => {
  close(midiToHz(69), 440);
  close(midiToHz(81), 880);
  close(midiToHz(60), 261.6255653005986, 1e-9);
});

test("partials apply inharmonicity", () => {
  const inst = { partials: [[1, 1, 0], [6, 0.5, 1]], inharmonicity: 0.001, detune_cents: 0 };
  const [p1, p6] = partialList(inst, 57);
  close(p1.freq, 220 * Math.sqrt(1.001));
  close(p6.freq, 220 * 6 * Math.sqrt(1 + 0.001 * 36));
  assert.equal(p6.amp, 0.5);
  assert.equal(p6.decay, 1);
});

test("detune doubles oscillators at half amplitude", () => {
  const inst = { partials: [[1, 1, 0]], inharmonicity: 0, detune_cents: 6 };
  const ps = partialList(inst, 69);
  assert.equal(ps.length, 2);
  assert.ok(ps[0].freq < 440 && ps[1].freq > 440);
  assert.equal(ps[0].amp, 0.5);
});

test("partials above Nyquist are dropped", () => {
  const inst = { partials: [[1, 1, 0], [100, 1, 0]], inharmonicity: 0, detune_cents: 0 };
  assert.equal(partialList(inst, 100, 44100).length, 1);
});

test("noteLevel follows gain * vel^1.5", () => {
  close(noteLevel({ gain: 0.6 }, 0.5), 0.6 * 0.5 ** 1.5);
  close(noteLevel({}, 1), 1);
});

test("impulse is deterministic, unit energy, and decays", () => {
  const a = impulseData(1000, 2);
  const b = impulseData(1000, 2);
  assert.equal(a.length, 2000);
  assert.deepEqual(a, b);
  close(a.reduce((s, v) => s + v * v, 0), 1, 1e-6);
  const head = a.slice(0, 200).reduce((s, v) => s + v * v, 0);
  const tail = a.slice(1800).reduce((s, v) => s + v * v, 0);
  assert.ok(tail < head / 1000);
});

test("voiceToSteal picks the oldest sounding voice only at the cap", () => {
  const voices = Array.from({ length: MAX_VOICES }, (_, i) => ({ start: i, end: 1000 }));
  assert.equal(voiceToSteal(voices, 100).start, 0);
  assert.equal(voiceToSteal(voices.slice(1), 100), null);
  assert.equal(voiceToSteal([{ start: 0, end: 5 }], 10, 1), null);
});
