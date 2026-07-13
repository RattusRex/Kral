import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const main = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("player class editor preserves the earned character level", () => {
  assert.match(main, /lockedTotalLevel=\{edit \? form\.level : undefined\}/);
  assert.match(main, /Сумма уровней классов должна быть равна/);
  assert.match(main, /level: edit\s*\? current\.level/);
  assert.match(main, /disabled=\{edit && form\.class_levels\.reduce/);
});
