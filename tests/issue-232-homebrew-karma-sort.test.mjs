import assert from "node:assert/strict";
import test from "node:test";

import { compareHomebrewKarma, nextHomebrewSort } from "../app/src/homebrewSort.js";

const entry = (karma_cost, { id = 1, is_banned = false } = {}) => ({ id, karma_cost, is_banned });

test("karma costs sort numerically in both directions", () => {
  const entries = [5, 60, 35, 20, 10].map((cost, index) => entry(cost, { id: index + 1 }));

  assert.deepEqual(entries.toSorted((left, right) => compareHomebrewKarma(left, right, "desc")).map(({ karma_cost }) => karma_cost), [60, 35, 20, 10, 5]);
  assert.deepEqual(entries.toSorted((left, right) => compareHomebrewKarma(left, right, "asc")).map(({ karma_cost }) => karma_cost), [5, 10, 20, 35, 60]);
});

test("ranges use their first numeric bound while special values remain last", () => {
  const entries = [
    entry("25–30", { id: 1 }),
    entry(20, { id: 2 }),
    entry("???", { id: 3 }),
    entry(null, { id: 4, is_banned: true }),
    entry(null, { id: 5 }),
  ];

  assert.deepEqual(entries.toSorted((left, right) => compareHomebrewKarma(left, right, "desc")).map(({ id }) => id), [1, 2, 3, 5, 4]);
  assert.deepEqual(entries.toSorted((left, right) => compareHomebrewKarma(left, right, "asc")).map(({ id }) => id), [2, 1, 3, 5, 4]);
});

test("a newly selected column starts descending and then toggles", () => {
  assert.deepEqual(nextHomebrewSort({ field: "title", direction: "asc" }, "karma_cost"), { field: "karma_cost", direction: "desc" });
  assert.deepEqual(nextHomebrewSort({ field: "karma_cost", direction: "desc" }, "karma_cost"), { field: "karma_cost", direction: "asc" });
  assert.deepEqual(nextHomebrewSort({ field: "karma_cost", direction: "asc" }, "karma_cost"), { field: "karma_cost", direction: "desc" });
});
