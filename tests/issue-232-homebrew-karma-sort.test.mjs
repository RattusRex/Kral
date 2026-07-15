import assert from "node:assert/strict";
import test from "node:test";

import {
  compareHomebrewKarma,
  homebrewKarmaSortKey,
  nextHomebrewSort,
} from "../app/src/homebrewSort.js";

const entries = [
  { id: 1, karma_cost: 5, is_banned: false },
  { id: 2, karma_cost: 60, is_banned: false },
  { id: 3, karma_cost: 35, is_banned: false },
  { id: 4, karma_cost: null, is_banned: true },
  { id: 5, karma_cost: null, is_banned: false, status_text: "???" },
  { id: 6, karma_cost: null, is_banned: false, status_text: "25–30 кармы" },
  { id: 7, karma_cost: "30-35 кармы", is_banned: false },
];

test("karma sort orders numeric values numerically in both directions", () => {
  assert.deepEqual(
    entries.slice(0, 3).sort((a, b) => compareHomebrewKarma(a, b, "desc")).map(({ karma_cost }) => karma_cost),
    [60, 35, 5],
  );
  assert.deepEqual(
    entries.slice(0, 3).sort((a, b) => compareHomebrewKarma(a, b, "asc")).map(({ karma_cost }) => karma_cost),
    [5, 35, 60],
  );
});

test("karma sort handles ranges, bans, and unknown values predictably", () => {
  assert.deepEqual(homebrewKarmaSortKey(entries[3]), { group: 1, value: 0 });
  assert.deepEqual(homebrewKarmaSortKey(entries[4]), { group: 2, value: 0 });
  assert.deepEqual(homebrewKarmaSortKey(entries[5]), { group: 0, value: 25 });
  assert.deepEqual(homebrewKarmaSortKey(entries[6]), { group: 0, value: 30 });
  assert.deepEqual(
    entries.slice(3).sort((a, b) => compareHomebrewKarma(a, b, "desc")).map(({ id }) => id),
    [7, 6, 4, 5],
  );
});

test("karma column sorts descending on first click and then toggles", () => {
  const initial = { field: "title", direction: "asc" };
  const descending = nextHomebrewSort(initial, "karma_cost");
  assert.deepEqual(descending, { field: "karma_cost", direction: "desc" });
  assert.deepEqual(nextHomebrewSort(descending, "karma_cost"), { field: "karma_cost", direction: "asc" });
});
