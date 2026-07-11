import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("every numeric input keeps the user's raw value while editing", () => {
  const numericInputs = [...source.matchAll(/<input\b[\s\S]*?type="number"[\s\S]*?\/>/g)]
    .map((match) => match[0]);

  assert.equal(numericInputs.length, 14, "update this coverage when adding numeric inputs");
  for (const input of numericInputs) {
    assert.match(input, /onChange=\{numericInputChange\(/, input);
    assert.doesNotMatch(input, /onChange=\{\(event\)[\s\S]*Number\(event\.target\.value\)/, input);
  }
});

test("numeric input normalization is deferred until blur or form submission", () => {
  assert.match(source, /function numericInputChange[\s\S]*event\.target\.value/);
  assert.match(source, /function normalizeNumber[\s\S]*Number\(value\)/);
  assert.match(source, /function normalizeNumberOnBlur[\s\S]*event\.target\.value[\s\S]*normalizeNumber/);
});
