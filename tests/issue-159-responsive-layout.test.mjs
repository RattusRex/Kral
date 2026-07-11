import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../app/src/styles.css", import.meta.url), "utf8");

test("shared components prevent long dynamic content from overflowing", () => {
  assert.match(styles, /overflow-wrap:\s*anywhere/);
  assert.match(styles, /\.panel[\s\S]*min-width:\s*0/);
  assert.match(styles, /\.field[\s\S]*min-width:\s*0/);
  assert.match(styles, /\.btn[\s\S]*white-space:\s*normal/);
  assert.match(styles, /\.responsive-table[\s\S]*overflow-x:\s*auto/);
});

test("skill rows stack their controls before labels can overlap", () => {
  assert.match(source, /className="skill-row [^"]*"/);
  assert.match(source, /className="skill-roll [^"]*"/);
  assert.match(source, /className="skill-options"/);
  assert.match(styles, /@media \(max-width:\s*639px\)[\s\S]*\.skill-row[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)/);
});

test("wide data tables use the shared accessible scroll region", () => {
  const wideTables = [...source.matchAll(/<table className="[^"]*min-w-\[[^"]*"/g)];
  const responsiveRegions = [...source.matchAll(/className="responsive-table(?: [^"]*)?"/g)];

  assert.ok(wideTables.length >= 6, "keep this audit aligned with every wide table");
  assert.equal(responsiveRegions.length, wideTables.length);
});

test("dense action groups wrap on narrow viewports", () => {
  assert.doesNotMatch(source, /className="mt-4 flex gap-2"/);
  assert.doesNotMatch(source, /className="flex gap-2 md:col-span-2"/);
  assert.doesNotMatch(source, /className="mt-2 flex gap-2"/);
});
