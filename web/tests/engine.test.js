import assert from "node:assert/strict";
import test from "node:test";

import { Engine } from "../engine.js";

class FakeWorker {
  constructor() {
    this.sent = [];
    this.onmessage = null;
  }
  postMessage(msg) {
    this.sent.push(msg);
  }
  reply(msg) {
    this.onmessage({ data: msg });
  }
}

test("compose resolves with the worker's result", async () => {
  const w = new FakeWorker();
  const engine = new Engine(w);
  const promise = engine.compose({ style: "tonal" });
  assert.equal(w.sent[0].op, "compose");
  w.reply({ id: w.sent[0].id, ok: true, result: { notes: [] } });
  assert.deepEqual(await promise, { notes: [] });
});

test("newest request wins while busy", async () => {
  const w = new FakeWorker();
  const engine = new Engine(w);
  const first = engine.compose({ seed: 1 });
  const second = engine.compose({ seed: 2 });
  const third = engine.compose({ seed: 3 });
  assert.equal(w.sent.length, 1, "only one compose in flight");
  assert.equal(await second, null, "replaced request resolves null");
  w.reply({ id: w.sent[0].id, ok: true, result: "one" });
  assert.equal(await first, null, "the running request was replaced too");
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(w.sent.length, 2);
  assert.deepEqual(w.sent[1].params, { seed: 3 });
  w.reply({ id: w.sent[1].id, ok: true, result: "three" });
  assert.equal(await third, "three");
});

test("errors reject with kind", async () => {
  const w = new FakeWorker();
  const engine = new Engine(w);
  const promise = engine.compose({});
  w.reply({ id: w.sent[0].id, ok: false, kind: "value", error: "tempo must be between 40 and 200" });
  await assert.rejects(promise, (err) => err.kind === "value" && /tempo/.test(err.message));
});

test("progress messages go to onProgress", () => {
  const w = new FakeWorker();
  const seen = [];
  new Engine(w, { onProgress: (p) => seen.push(p) });
  w.reply({ progress: 0.5, stage: "Loading numpy" });
  assert.deepEqual(seen, [{ progress: 0.5, stage: "Loading numpy" }]);
});

test("a running compose replaced by a newer request resolves null", async () => {
  const w = new FakeWorker();
  const engine = new Engine(w);
  const first = engine.compose({ seed: 1 });
  const second = engine.compose({ seed: 2 });
  w.reply({ id: w.sent[0].id, ok: true, result: "stale" });
  assert.equal(await first, null, "stale result is not applied");
  await new Promise((r) => setTimeout(r, 0));
  w.reply({ id: w.sent[1].id, ok: true, result: "fresh" });
  assert.equal(await second, "fresh");
});
