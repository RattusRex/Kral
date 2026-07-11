import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("server rule publications start collapsed, expand independently, and persist for the session", () => {
  assert.match(source, /expandedContentBlocks/);
  assert.match(source, /useState<number\[\]>\(\(\) => readExpandedContentBlocks\(pageSlug\)\)/);
  assert.match(source, /function readExpandedContentBlocks/);
  assert.match(source, /sessionStorage\.getItem/);
  assert.match(source, /sessionStorage\.setItem/);
  assert.match(source, /content-blocks-expanded-\$\{pageSlug\}/);
  assert.match(source, /toggleContentBlock/);
  assert.match(source, /const isExpanded = expandedContentBlocks\.includes\(block\.id\)/);
  assert.doesNotMatch(source, /collapsedContentBlocks/);
});

test("every publication exposes an accessible disclosure control", () => {
  assert.match(source, /aria-controls={`content-block-\$\{block\.id\}`}/);
  assert.match(source, /aria-expanded={isExpanded}/);
  assert.match(source, /id={`content-block-\$\{block\.id\}`}/);
  assert.match(source, /isExpanded \? <ChevronUp/);
  assert.match(source, /: <ChevronDown/);
});
