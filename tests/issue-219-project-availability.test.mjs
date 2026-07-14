import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("owner project management displays and updates selection availability", () => {
  assert.match(source, /Доступен пользователям/);
  assert.match(source, /\/projects\/\$\{project\.id\}\/availability/);
  assert.match(source, /is_selectable/);
});
