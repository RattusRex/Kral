import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("every numeric input keeps the user's raw value while editing", () => {
  const inputStarts = [...source.matchAll(/<input\b/g)].map((match) => match.index);
  const numericInputs = inputStarts.map((start) => {
    let end = start;
    let braces = 0;
    for (; end < source.length; end += 1) {
      if (source[end] === "{") braces += 1;
      if (source[end] === "}") braces -= 1;
      if (source.startsWith("/>", end) && braces === 0) return source.slice(start, end + 2);
    }
    return "";
  }).filter((input) => input.includes('type="number"'));

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
