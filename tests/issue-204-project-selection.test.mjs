import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("login clears stale context and routes to mandatory project selection", () => {
  assert.match(source, /localStorage\.removeItem\(PROJECT_KEY\)[\s\S]*navigate\("\/projects"\)/);
});

test("project selection is a dedicated protected route", () => {
  assert.match(source, /function ProjectSelectionPage\(/);
  assert.match(source, /path="\/projects"/);
  assert.match(source, /Выберите проект/);
});

test("game routes reject authenticated sessions without an active project", () => {
  assert.match(source, /function ProjectProtected\(/);
  assert.match(source, /<ProjectProtected>/);
});
