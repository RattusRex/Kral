import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const apiSource = readFileSync(new URL("../app/src/api.ts", import.meta.url), "utf8");

test("project settings expose all optional project systems", () => {
  for (const feature of ["leaderboard", "karma", "karma_logs", "character_transfers", "market_logs", "logs"]) {
    assert.match(source, new RegExp(`${feature}:`));
    assert.match(apiSource, new RegExp(`${feature}: boolean`));
  }
});

test("optional systems are hidden by project feature flags", () => {
  assert.match(source, /features\.leaderboard !== false/);
  assert.match(source, /features\.karma !== false/);
  assert.match(source, /features\.karma_logs !== false/);
  assert.match(source, /features\.character_transfers !== false/);
  assert.match(source, /features\.market_logs !== false/);
  assert.match(source, /features\.logs !== false/);
});
