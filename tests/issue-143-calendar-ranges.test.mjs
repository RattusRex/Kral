import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";

const source = fs.readFileSync("app/src/main.tsx", "utf8");
const apiSource = fs.readFileSync("app/src/api.ts", "utf8");
const calendarPanel = source.slice(
  source.indexOf("function CalendarPanel"),
  source.indexOf("function CharacterPage()")
);
const characterPage = source.slice(
  source.indexOf("function CharacterPage()"),
  source.indexOf("function CharacterFormPage")
);

test("calendar API entries expose their inclusive end date", () => {
  assert.match(apiSource, /interface DowntimeEntry[\s\S]*end_date: string/);
});

test("shared calendar journal displays start, end, and total busy days", () => {
  assert.match(
    calendarPanel,
    /formatGameDate\(entry\.start_date\)[\s\S]*formatGameDate\(entry\.end_date\)[\s\S]*Всего:[\s\S]*entry\.days/
  );
});

test("the range display belongs to the panel shared by every calendar actor", () => {
  assert.match(calendarPanel, /agentType = "character"/);
  assert.match(calendarPanel, /const canManage = summary\?\.can_manage/);
  assert.match(characterPage, /<CalendarPanel characterId=\{id\}/);
  assert.match(characterPage, /agentType="personal_hireling"/);
  assert.match(characterPage, /agentType="simulacrum"/);
});
