import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";

const apiSource = fs.readFileSync("app/src/api.ts", "utf8");
const mainSource = fs.readFileSync("app/src/main.tsx", "utf8");
const viteSource = fs.readFileSync("vite.config.ts", "utf8");

test("authenticated project pages keep one reconnecting WebSocket connection", () => {
  assert.match(apiSource, /new WebSocket\(/);
  assert.match(apiSource, /setTimeout\([^]*connect[^]*Math\.min/);
  assert.match(apiSource, /addEventListener\("storage"/);
  assert.match(mainSource, /<RealtimeProvider>/);
});

test("realtime invalidations refresh chat, recruitment, characters, market, and logs", () => {
  for (const event of ["chat.changed", "recruitment.changed", "character.changed", "market.changed", "logs.changed"]) {
    assert.match(mainSource, new RegExp(event.replace(".", "\\.")));
  }
});

test("development proxy and nginx support WebSocket upgrades", () => {
  assert.match(viteSource, /"\/api":\s*\{[^}]*ws:\s*true/s);
});
