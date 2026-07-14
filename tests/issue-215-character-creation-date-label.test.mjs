import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const calendarPanel = source.slice(
  source.indexOf("function CalendarPanel("),
  source.indexOf("function CharacterPage()"),
);
const characterForm = source.slice(
  source.indexOf("function CharacterFormPage("),
  source.indexOf("function ShopPage()"),
);
const adminCharacterPage = source.slice(
  source.indexOf("function AdminCharacterPage()"),
  source.indexOf("function AdminGrantLogsPage()"),
);

test("character creation date uses the correct label on every relevant surface", () => {
  assert.match(calendarPanel, /agentType === "personal_hireling"[\s\S]*?: "Дата создания"/);
  assert.match(characterForm, /Дата создания персонажа/);
  assert.match(
    adminCharacterPage,
    /<Stat label="Дата создания" value=\{formatGameDate\(character\.game_created_at\)\} \/>/,
  );
});

test("the obsolete assembled-date label is absent from the production UI", () => {
  assert.doesNotMatch(source, /Дата сбора/);
});
