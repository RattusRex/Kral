import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("about page is reachable from project selection, top navigation, and menu", () => {
  assert.match(source, /function choose\([\s\S]*navigate\("\/about"\)/);
  assert.match(source, /function selectProject\([\s\S]*window\.location\.assign\("\/about"\)/);
  assert.match(source, /<Link className="btn-secondary" to="\/about">[\s\S]*О проекте/);
  assert.match(source, /function HomePage\([\s\S]*<Link className="btn" to="\/about">[\s\S]*О проекте/);
});

test("about page renders a responsive post feed and independent creator sidebar", () => {
  assert.match(source, /function ProjectAboutPage/);
  assert.match(source, /about\.posts\.map/);
  assert.match(source, /О создателе/);
  assert.match(source, /lg:grid-cols-\[minmax\(0,1fr\)_320px\]/);
});

test("only head admins and owners receive about management controls", () => {
  assert.match(source, /canManageAbout[\s\S]*is_owner[\s\S]*project_owner[\s\S]*head_admin/);
  assert.doesNotMatch(source, /project\?\.is_admin[\s\S]{0,200}(Создать публикацию|Редактировать)/);
});
