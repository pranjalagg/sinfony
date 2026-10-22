// One-click examples: each is a share-link state plus a "listen for" hint.

import { encodeHash } from "./share.js";

const isText = (v) => typeof v === "string";
const isExample = (e) =>
  e !== null && typeof e === "object" && isText(e.id) && isText(e.name) && isText(e.listen) &&
  e.params !== null && typeof e.params === "object";

/** The examples from examples.json, or [] when the file can't be loaded or isn't a valid list. */
export async function loadExamples(fetchFn = fetch, url = "examples.json") {
  try {
    const res = await fetchFn(url);
    if (!res.ok) return [];
    const list = await res.json();
    return Array.isArray(list) && list.every(isExample) ? list : [];
  } catch {
    return [];
  }
}

/** The share-link hash that opens this example. */
export function exampleHash(example) {
  const p = example.params;
  return encodeHash({
    style: p.style, seed: p.seed, key: p.key ?? null, tempo: p.tempo ?? null, wiggle: p.wiggle ?? null,
    smooth: p.smooth ?? null, density: p.density ?? null, contour: p.contour ?? {}, tension: p.tension ?? null,
  });
}
