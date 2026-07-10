import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("ranger class is available with a d8 hit die", () => {
  assert.match(source, /\{ name: "Егерь", hitDie: "d8" \}/);
});

test("character forms expose saving throw proficiency controls", () => {
  assert.match(source, /saving_throw_proficiencies/);
  assert.match(source, /Владение спасброском/);
});

test("admin form exposes the character appearance date", () => {
  assert.match(source, /field: "game_created_at", label: "Дата появления персонажа"/);
});

test("delete controls are limited to owner and head admin", () => {
  assert.match(source, /user\?\.is_owner \|\| user\?\.is_head_admin/);
});
