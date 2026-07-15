import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("project selection opens the project about page", () => {
  assert.match(source, /navigate\("\/about-project"\)/);
  assert.match(source, /path="\/about-project"/);
});

test("navigation exposes the project about page", () => {
  assert.match(source, /to="\/about-project"[^>]*>.*О проекте/);
});

test("about page renders project content and technician editing controls", () => {
  assert.match(source, /function ProjectAboutPage/);
  assert.match(source, /ROLE_RANK\[project\.role/);
  assert.match(source, /ROLE_RANK\.technician/);
  assert.match(source, /\/projects\/about/);
  assert.match(source, /markdownToHtml/);
  assert.match(source, /Редактировать/);
  assert.match(source, /Сохранить/);
});

test("about page uses a responsive wrapping title", () => {
  assert.match(source, /break-words/);
  assert.match(source, /text-3xl[^"\n]*md:text-5xl/);
});
