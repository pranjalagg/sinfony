import assert from "node:assert/strict";
import test from "node:test";

import { loadTheme, nextTheme } from "../theme.js";

test("light unless dark was chosen", () => {
  assert.equal(loadTheme({ getItem: () => null }), "light");
  assert.equal(loadTheme({ getItem: () => "dark" }), "dark");
  assert.equal(loadTheme({ getItem: () => "garbage" }), "light");
});

test("blocked storage falls back to light", () => {
  assert.equal(loadTheme({ getItem: () => { throw new Error("blocked"); } }), "light");
  assert.equal(loadTheme(undefined), "light");
});

test("nextTheme flips", () => {
  assert.equal(nextTheme("light"), "dark");
  assert.equal(nextTheme("dark"), "light");
});
