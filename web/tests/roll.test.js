import assert from "node:assert/strict";
import test from "node:test";

import { FN_COLOR, MIN_LABEL_PX, chordPills, legendItems } from "../roll.js";

const x = (beat) => beat * 10;
const chord = (onset, dur, fn, label = "I") => ({ onset, dur, label, function: fn });

test("chordPills spans each chord", () => {
  const pills = chordPills([chord(0, 4, "T"), chord(4, 4, "D", "V")], x);
  assert.deepEqual(
    pills.map(({ x0, x1, label, colorKey }) => ({ x0, x1, label, colorKey })),
    [
      { x0: 0, x1: 40, label: "I", colorKey: "fnHome" },
      { x0: 40, x1: 80, label: "V", colorKey: "fnTension" },
    ],
  );
});

test("chordPills hides labels that do not fit", () => {
  const [narrow, wide] = chordPills([chord(0, 1, "T"), chord(1, 4, "T")], x);
  assert.ok(10 < MIN_LABEL_PX);
  assert.equal(narrow.showLabel, false);
  assert.equal(wide.showLabel, true);
});

test("unknown function falls back to neutral", () => {
  assert.equal(chordPills([chord(0, 4, "other")], x)[0].colorKey, "chordNeutral");
  assert.equal(chordPills([chord(0, 4, "???")], x)[0].colorKey, "chordNeutral");
  assert.equal(FN_COLOR.S, "fnAway");
});

test("legendItems tonal", () => {
  const items = legendItems("tonal");
  assert.deepEqual(items.map((i) => i.colorKey), ["fnHome", "fnAway", "fnTension"]);
  assert.ok(items[0].text.includes("Home (I, iii, vi)"));
  assert.ok(items[1].text.includes("Away (ii, IV, V/V)"));
  assert.ok(items[2].text.includes("Tension (V, V7, vii°)"));
});

test("legendItems ambient", () => {
  const items = legendItems("ambient");
  assert.equal(items.length, 1);
  assert.equal(items[0].colorKey, "chordNeutral");
  assert.equal(items[0].text, "Each chord moves to a close neighbor on the Tonnetz (P, L, or R).");
});
