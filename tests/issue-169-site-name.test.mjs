import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const html = await readFile(new URL("../app/frontend/index.html", import.meta.url), "utf8");

test("browser and sharing metadata use the current project name", () => {
  assert.match(html, /<title>Epoha Kostyastrof<\/title>/);
  assert.match(html, /<meta name="application-name" content="Epoha Kostyastrof" \/>/);
  assert.match(html, /<meta property="og:site_name" content="Epoha Kostyastrof" \/>/);
  assert.match(html, /<meta property="og:title" content="Epoha Kostyastrof" \/>/);
});

test("the retired site name is absent from the page shell", () => {
  assert.doesNotMatch(html, /Kral RPG/i);
});
