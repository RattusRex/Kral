import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("character sheet implements every proficiency bonus tier", () => {
  assert.match(source, /function proficiencyBonus\(level: number\)/);
  assert.match(source, /2 \+ Math\.floor\(\(Math\.max\(1, Math\.min\(20, level\)\) - 1\) \/ 4\)/);
  assert.match(source, /Бонус мастерства/);
});

test("character sheet shows all eighteen D&D 5e skills", () => {
  const keys = [
    "acrobatics", "animal_handling", "arcana", "athletics", "deception",
    "history", "insight", "intimidation", "investigation", "medicine",
    "nature", "perception", "performance", "persuasion", "religion",
    "sleight_of_hand", "stealth", "survival"
  ];
  for (const key of keys) assert.match(source, new RegExp(`key: "${key}"`));
});

test("expertise control depends on proficiency and doubles only proficiency bonus", () => {
  assert.match(source, /disabled=\{!proficient\}/);
  assert.match(source, /expert \? bonus \* 2 : proficient \? bonus : 0/);
  assert.match(source, /expertise\.filter\(\(key\) => key !== skill\.key\)/);
});
