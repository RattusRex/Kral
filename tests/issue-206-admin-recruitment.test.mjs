import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const recruitmentPage = source.slice(
  source.indexOf("function GameRecruitmentsPage()"),
  source.indexOf("function ChatPage()"),
);

test("recruitment managers retain an independent signup form", () => {
  assert.match(recruitmentPage, /recruitment\.can_manage &&[\s\S]*?Выдать выбранных игроков/);
  assert.match(
    recruitmentPage,
    /recruitment\.status === "upcoming" && recruitment\.application_status === "not_applied"[\s\S]*?Записаться/,
  );
  assert.doesNotMatch(
    recruitmentPage,
    /recruitment\.can_manage \? \([\s\S]*?Выдать выбранных игроков[\s\S]*?\) : recruitment\.status/,
  );
});
