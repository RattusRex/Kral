import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const homePage = source.slice(
  source.indexOf("function HomePage()"),
  source.indexOf("const PROJECT_FEATURE_LABELS"),
);

test("home menu uses Russian labels for the magic shop and character list", () => {
  assert.match(homePage, /to="\/shop"[^>]*>[\s\S]*?Магический магазин<\/Link>/);
  assert.match(homePage, /to="\/characters"[^>]*>[\s\S]*?Мои персонажи<\/Link>/);
  assert.doesNotMatch(homePage, />Shop<\/Link>/);
  assert.doesNotMatch(homePage, />My Characters<\/Link>/);
});

test("home menu does not duplicate character creation", () => {
  assert.doesNotMatch(homePage, /to="\/characters\/new"/);
  assert.doesNotMatch(homePage, />Create Character<\/Link>/);
});
