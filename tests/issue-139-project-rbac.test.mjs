import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const api = readFileSync(new URL("../app/src/api.ts", import.meta.url), "utf8");
const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("project role hierarchy and selected-project header are exposed by the client", () => {
  assert.match(api, /project_owner.*head_admin.*admin.*technician.*player/);
  assert.match(api, /X-Project-ID/);
  assert.match(api, /active_project_id/);
});

test("project selector, settings page, and feature-aware navigation are rendered", () => {
  assert.match(source, /aria-label="Проект"/);
  assert.match(source, /path="\/project-settings"/);
  assert.match(source, /project\?\.features\.shop !== false/);
  assert.match(source, /PROJECT_FEATURE_LABELS/);
});

test("technician is offered to every role manager", () => {
  assert.match(source, /ROLE_OPTIONS[^;]+technician/);
  assert.match(source, /HEAD_ADMIN_ASSIGNABLE_ROLES[^;]+technician/);
});
