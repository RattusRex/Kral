import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("choosing or switching a project opens its about page", () => {
  assert.match(source, /function choose\([\s\S]*navigate\("\/about"\)/);
  assert.match(source, /function selectProject\([\s\S]*window\.location\.assign\("\/about"\)/);
  assert.match(source, /path="\/about"/);
});

test("project about page exposes responsive formatted content and restricted editing", () => {
  assert.match(source, /function ProjectAboutPage/);
  assert.match(source, /\/projects\/current\/about/);
  assert.match(source, /canManageAbout/);
  assert.match(source, /Редактировать/);
  assert.match(source, /sm:text-4xl/);
  assert.match(source, /MarkdownContent/);
});
