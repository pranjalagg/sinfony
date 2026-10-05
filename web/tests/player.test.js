import assert from "node:assert/strict";
import test from "node:test";

import { Player, beatAtSeconds, notesInWindow, secondsAtBeat, swapPosition } from "../player.js";

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);
const halfSecondBeats = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4];

test("beat <-> seconds interpolation and inverse", () => {
  close(secondsAtBeat(halfSecondBeats, 3), 1.5);
  close(secondsAtBeat(halfSecondBeats, 2.5), 1.25);
  close(beatAtSeconds(halfSecondBeats, 1.25), 2.5);
  close(beatAtSeconds(halfSecondBeats, 5), 10); // extrapolates past the end
  close(secondsAtBeat(halfSecondBeats, -1), -0.5);
});

test("notesInWindow is half-open", () => {
  const notes = [0, 0.1, 0.2, 0.3].map((onset_s) => ({ onset_s }));
  assert.deepEqual(notesInWindow(notes, 0.1, 0.3).map((n) => n.onset_s), [0.1, 0.2]);
});

test("swapPosition keeps the beat when the tempo changes", () => {
  const old = { beat_s: halfSecondBeats };
  const quick = { beat_s: halfSecondBeats.map((s) => s / 2) };
  close(swapPosition(old, quick, 2), 1); // beat 4 in both pieces
});

function fakeWorld() {
  const ctx = { currentTime: 10 };
  const calls = [];
  const synth = {
    noteOn: (inst, pitch, vel, when, dur) => calls.push({ pitch, when, dur }),
    cancelAfter: (t) => calls.push({ cancelAfter: t }),
    stopAll: () => calls.push({ stopAll: true }),
    setReverb: () => {},
  };
  return { ctx, synth, calls };
}

const piece = (beatSeconds, onsets) => ({
  beat_s: Array.from({ length: 9 }, (_, i) => i * beatSeconds),
  duration_s: 8 * beatSeconds,
  notes: onsets.map((b, i) => ({ voice: "melody", pitch: 60 + i, vel: 0.8, onset_s: b * beatSeconds, dur_s: 0.1 })),
  voices: [{ name: "melody", instrument: "epiano" }],
  instruments: { epiano: { partials: [[1, 1, 1]], attack: 0.01, release: 0.1, gain: 1 } },
  reverb: { seconds: 1, mix: 0.2 },
});

test("player schedules the look-ahead window on the audio clock", () => {
  const { ctx, synth, calls } = fakeWorld();
  const p = new Player(ctx, synth);
  p.load(piece(0.5, [0, 0.1, 1]));
  p.play();
  const first = calls.filter((c) => c.pitch !== undefined);
  assert.deepEqual(first.map((c) => c.pitch), [60, 61]); // onsets 0 s and 0.05 s are within 0.1 s
  close(first[0].when, p.origin);
  p.stop();
});

test("hot swap continues from the same beat", () => {
  const { ctx, synth, calls } = fakeWorld();
  const p = new Player(ctx, synth);
  p.load(piece(0.5, [0, 4, 6]));
  p.play();
  ctx.currentTime += 2.05; // play() starts 0.05 s ahead, so this is 2 s in = beat 4 at 0.5 s per beat
  p.load(piece(0.25, [0, 4, 6])); // twice as fast: beat 4 is at 1 s
  close(p.position, 1, 1e-6);
  assert.ok(calls.some((c) => c.cancelAfter !== undefined));
  p.tick();
  const scheduled = calls.filter((c) => c.pitch !== undefined).map((c) => c.pitch);
  assert.ok(scheduled.includes(61), "note at beat 4 plays in the new piece");
  p.stop();
});

test("player stops at the end unless looping", () => {
  const { ctx, synth } = fakeWorld();
  let ended = 0;
  const p = new Player(ctx, synth, { onEnd: () => ended++ });
  p.load(piece(0.5, [0]));
  p.play();
  ctx.currentTime += 5;
  p.tick();
  assert.equal(p.playing, false);
  assert.equal(ended, 1);
  p.loop = true;
  p.play();
  ctx.currentTime += 5;
  p.tick();
  assert.equal(p.playing, true);
  close(p.position, 0, 0.06);
  p.stop();
});
