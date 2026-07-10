import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";

const source = fs.readFileSync("app/src/main.tsx", "utf8");
const characterPage = source.slice(
  source.indexOf("function CharacterPage()"),
  source.indexOf("function CharacterFormPage")
);

test("player character sheet shows granted unit calendars", () => {
  assert.match(
    characterPage,
    /character\.personal_hireling_enabled\s*&&[\s\S]*agentType="personal_hireling"[\s\S]*Календарь личного наёмника/
  );
  assert.match(
    characterPage,
    /character\.simulacrum_enabled\s*&&[\s\S]*agentType="simulacrum"[\s\S]*Календарь симулякра/
  );
});

test("unit calendars hide every mutation control from players", () => {
  const calendarPanel = source.slice(
    source.indexOf("function CalendarPanel"),
    source.indexOf("function CharacterPage()")
  );

  assert.match(calendarPanel, /const isUnitCalendar = agentType !== "character"/);
  assert.match(calendarPanel, /!isUnitCalendar\s*&&\s*\([\s\S]*onSubmit=\{addEntry\}/);
  assert.match(calendarPanel, /canManage\s*&&[\s\S]*Изменить[\s\S]*Удалить/);
});
