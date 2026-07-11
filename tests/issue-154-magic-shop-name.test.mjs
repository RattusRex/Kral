import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("magic shop uses its full display name on every navigation surface", () => {
  const labels = [
    /to="\/shop"[^>]*>[\s\S]*?Магический магазин<\/Link>/,
    /to={`\/shop\?character=\$\{character\.id\}`}[^>]*>Магический магазин<\/Link>/,
    /<h1[^>]*>Магический магазин<\/h1>/,
    /shop: "Магический магазин"/,
  ];

  for (const label of labels) assert.match(source, label);
  assert.doesNotMatch(source, />Магазин<\/Link>/);
  assert.doesNotMatch(source, />Магазин<\/h1>/);
  assert.doesNotMatch(source, /shop: "Магазин"/);
});

test("renaming the shop leaves its route and feature key unchanged", () => {
  assert.match(source, /features\.shop !== false/);
  assert.match(source, /<Route path="\/shop"/);
});
