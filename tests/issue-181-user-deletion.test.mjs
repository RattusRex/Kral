import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("only owners see user deletion and must confirm the destructive action", () => {
  assert.match(source, /user\?\.is_owner && row\.id !== user\.id/);
  assert.match(source, /window\.confirm\(`Удалить пользователя «\$\{row\.username\}» и все связанные данные\?/);
  assert.match(source, /api\.delete\(`\/admin\/users\/\$\{row\.id\}`\)/);
});
