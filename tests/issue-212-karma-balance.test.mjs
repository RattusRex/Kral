import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const karmaShopPage = source.slice(
  source.indexOf("function KarmaShopPage()"),
  source.indexOf("function LeaderboardPage()"),
);

test("karma shop uses its project-scoped balance for display and resurrection", () => {
  assert.match(karmaShopPage, /const \[karma, setKarma\] = useState\(0\)/);
  assert.match(karmaShopPage, /setKarma\(response\.data\.karma\)/);
  assert.match(karmaShopPage, /setKarma\(response\.data\.remaining_karma\)/);
  assert.match(karmaShopPage, /karma >= resurrectionCost/);
  assert.match(karmaShopPage, /Баланс: \{karma\} кармы/);
  assert.doesNotMatch(karmaShopPage, /\buser\b/);
});
