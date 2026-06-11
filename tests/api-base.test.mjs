import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { test } from "node:test";

import ts from "typescript";

async function loadApiBaseModule() {
  const source = fs.readFileSync("app/src/apiBase.ts", "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2020,
      target: ts.ScriptTarget.ES2020
    }
  });
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "kral-api-base-"));
  const modulePath = path.join(dir, "apiBase.mjs");
  fs.writeFileSync(modulePath, output.outputText);
  return import(pathToFileURL(modulePath));
}

test("production localhost static builds use the local FastAPI API by default", async () => {
  const { resolveApiBaseURL } = await loadApiBaseModule();

  assert.equal(
    resolveApiBaseURL({ DEV: false, PROD: true }, "http://localhost:3000"),
    "http://127.0.0.1:8000/api"
  );
});

test("development keeps relative API URL so Vite proxy handles requests", async () => {
  const { resolveApiBaseURL } = await loadApiBaseModule();

  assert.equal(
    resolveApiBaseURL(
      { DEV: true, PROD: false, VITE_API_TARGET: "http://127.0.0.1:9000" },
      "http://localhost:5173"
    ),
    "/api"
  );
});

test("production VITE_API_TARGET appends the API prefix", async () => {
  const { resolveApiBaseURL } = await loadApiBaseModule();

  assert.equal(
    resolveApiBaseURL(
      { DEV: false, PROD: true, VITE_API_TARGET: "https://backend.example.com/" },
      "https://app.example.com"
    ),
    "https://backend.example.com/api"
  );
});

test("explicit VITE_API_BASE_URL wins and is normalized", async () => {
  const { resolveApiBaseURL } = await loadApiBaseModule();

  assert.equal(
    resolveApiBaseURL(
      { DEV: false, PROD: true, VITE_API_BASE_URL: "https://api.example.com/api/" },
      "https://app.example.com"
    ),
    "https://api.example.com/api"
  );
});

test("non-local production builds keep same-origin API by default", async () => {
  const { resolveApiBaseURL } = await loadApiBaseModule();

  assert.equal(
    resolveApiBaseURL({ DEV: false, PROD: true }, "https://app.example.com"),
    "/api"
  );
});
