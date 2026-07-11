import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("server rule publications collapse independently and persist for the session", () => {
  assert.match(source, /collapsedContentBlocks/);
  assert.match(source, /sessionStorage\.getItem/);
  assert.match(source, /sessionStorage\.setItem/);
  assert.match(source, /content-blocks-collapsed-\$\{pageSlug\}/);
  assert.match(source, /toggleContentBlock/);
});

test("every publication exposes an accessible disclosure control", () => {
  assert.match(source, /aria-controls={`content-block-\$\{block\.id\}`}/);
  assert.match(source, /aria-expanded={!isCollapsed}/);
  assert.match(source, /id={`content-block-\$\{block\.id\}`}/);
  assert.match(source, /isCollapsed \? <ChevronDown/);
  assert.match(source, /: <ChevronUp/);
});
