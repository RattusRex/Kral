import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("character forms offer the Егерь class with a d8 hit die", () => {
  assert.match(source, /const characterClasses = \[[\s\S]*\{ name: "Егерь", hitDie: "d8" \}[\s\S]*\];/);
  assert.match(source, /<ClassSelect value=\{form\.class_name\}/);
});

test("character sheets display the selected class and its hit die", () => {
  assert.match(source, /<Stat label="Класс" value=\{character\.class_name\}/);
  assert.match(source, /<Stat label="Кость хитов" value=\{hitDieForClass\(character\.class_name\)\}/);
});
