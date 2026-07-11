import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const header = source.slice(
  source.indexOf("<header"),
  source.indexOf("</header>") + "</header>".length,
);
const homePage = source.slice(
  source.indexOf("function HomePage()"),
  source.indexOf("const PROJECT_FEATURE_LABELS"),
);

const gameRoutes = ["/shop", "/market", "/karma-shop", "/leaderboard"];

test("header omits game section links", () => {
  for (const route of gameRoutes) {
    assert.doesNotMatch(header, new RegExp(`to="${route}"`));
  }
});

test("main menu keeps game sections available", () => {
  for (const route of gameRoutes) {
    assert.match(homePage, new RegExp(`to="${route}"`));
  }
});
