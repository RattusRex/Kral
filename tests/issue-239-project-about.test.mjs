import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("choosing or switching a project opens its about page", () => {
  assert.match(source, /function choose\([\s\S]*navigate\("\/about"\)/);
  assert.match(source, /function selectProject\([\s\S]*window\.location\.assign\("\/about"\)/);
  assert.match(source, /path="\/about"/);
});

test("project about page exposes responsive title, formatted content, and role-aware editing", () => {
  assert.match(source, /function ProjectAboutPage/);
  assert.match(source, /\/projects\/current\/about/);
  assert.match(source, /project\?\.is_admin/);
  assert.match(source, /Редактировать/);
  assert.match(source, /text-4xl[\s\S]*md:text-6xl/);
  assert.match(source, /MarkdownContent/);
});
