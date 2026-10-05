import assert from "node:assert/strict";
import test from "node:test";

import {
  POINTS, applyStroke, cleanStroke, layoutSections, mergePads, pointU, sameLayout, smoothRange, strokeAt,
} from "../pads.js";

const flat = (v) => Array(POINTS).fill(v);
const tonalSections = [{ label: "A" }, { label: "A'" }, { label: "B" }, { label: "A" }];

test("layoutSections: equal widths without beats, proportional with beats", () => {
  const eq = layoutSections(tonalSections);
  assert.deepEqual(eq.map((s) => s.material), ["A", "A", "B", "A"]);
  assert.equal(eq[1].u0, 0.25);
  assert.equal(eq[3].u1, 1);
  const prop = layoutSections([
    { label: "A", material: "A", start: 0, end: 8 },
    { label: "A'", material: "A@3", start: 8, end: 32 },
  ]);
  assert.equal(prop[0].u1, 0.25);
  assert.equal(prop[1].material, "A@3");
});

test("pointU spans each section by cell centres", () => {
  const [sec] = layoutSections([{ label: "A" }]);
  assert.equal(pointU(sec, 0), 0.5 / POINTS);
  assert.equal(pointU(sec, POINTS - 1), 1 - 0.5 / POINTS);
});

test("cleanStroke sorts and clamps", () => {
  const s = cleanStroke([{ u: 0.5, y: 2 }, { u: 0.1, y: -1 }]);
  assert.deepEqual(s, [{ u: 0.1, y: 0 }, { u: 0.5, y: 1 }]);
});

test("strokeAt interpolates inside and is null outside", () => {
  const s = [{ u: 0.2, y: 0 }, { u: 0.4, y: 1 }];
  assert.ok(Math.abs(strokeAt(s, 0.3) - 0.5) < 1e-12);
  assert.equal(strokeAt(s, 0.1), null);
  assert.equal(strokeAt(s, 0.5), null);
});

test("smoothRange keeps the endpoints and averages inside", () => {
  const out = smoothRange([0, 0, 3, 0, 0], 0, 4);
  assert.deepEqual(out, [0, 1, 1, 1, 0]);
});

test("linked stroke writes one material shared by every section of it", () => {
  const sections = layoutSections(tonalSections);
  const values = { A: flat(0.5), B: flat(0.5) };
  const stroke = [{ u: 0, y: 1 }, { u: 0.25, y: 1 }];
  const { values: next, touched } = applyStroke(values, sections, stroke, true);
  assert.deepEqual([...touched], ["A"]);
  assert.ok(next.A.every((v) => v === 1));
  assert.equal(next.B, values.B);
  assert.ok(values.A.every((v) => v === 0.5), "input is not mutated");
});

test("unlinked stroke writes only the sections it crosses", () => {
  const sections = layoutSections(tonalSections);
  const values = Object.fromEntries(sections.map((_, i) => [String(i), flat(0.2)]));
  const stroke = [{ u: 0.2, y: 0.9 }, { u: 0.3, y: 0.9 }];
  const { values: next, touched } = applyStroke(values, sections, stroke, false);
  assert.deepEqual([...touched].sort(), ["0", "1"]);
  assert.equal(next["3"], values["3"]);
});

test("mergePads keeps drawn slots and fills the rest from defaults", () => {
  const defaults = { A: flat(0.3), B: flat(0.4) };
  const drawn = new Set(["A"]);
  const merged = mergePads(defaults, { A: flat(0.9), B: flat(0.5) }, drawn);
  assert.deepEqual(merged, { A: flat(0.9), B: flat(0.4) });
  assert.deepEqual(mergePads(defaults, {}, new Set(["A"])), defaults);
});

test("sameLayout compares materials in order", () => {
  const a = [{ material: "A" }, { material: "B" }];
  assert.ok(sameLayout(a, [{ material: "A" }, { material: "B" }]));
  assert.ok(!sameLayout(a, [{ material: "A" }, { material: "B" }, { material: "C" }]));
  assert.ok(!sameLayout(a, [{ material: "B" }, { material: "A" }]));
});
