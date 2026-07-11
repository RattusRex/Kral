import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";

const composeConfig = fs.readFileSync("docker-compose.yml", "utf8");
const exampleEnv = fs.readFileSync(".env.example", "utf8");
const developmentOverride = fs.readFileSync(
  "docker-compose.dev.yml",
  "utf8"
);

function extractService(text, serviceName) {
  const lines = text.split("\n");
  const serviceStart = lines.findIndex(
    (line) => line === `  ${serviceName}:`
  );
  assert.notEqual(serviceStart, -1, `missing ${serviceName} service`);

  const nextService = lines.findIndex(
    (line, index) => index > serviceStart && /^  [a-zA-Z0-9_-]+:$/.test(line)
  );
  const serviceEnd = nextService === -1 ? lines.length : nextService;

  return lines.slice(serviceStart + 1, serviceEnd).join("\n");
}

test("default compose keeps the backend on the internal network", () => {
  const backend = extractService(composeConfig, "backend");

  assert.doesNotMatch(
    backend,
    /^    ports:/m,
    "backend must not publish a host port in the default deployment"
  );
  assert.match(
    backend,
    /^    expose:\n      - "8000"$/m,
    "backend should remain reachable by nginx on the compose network"
  );
});

test("development override explicitly publishes the backend port", () => {
  const backend = extractService(developmentOverride, "backend");

  assert.match(
    backend,
    /^    ports:\n      - "8000:8000"$/m,
    "development override should opt in to direct FastAPI access"
  );
});

test("example environment satisfies the required email backend setting", () => {
  const backend = extractService(composeConfig, "backend");

  assert.match(
    backend,
    /^      EMAIL_BACKEND: \$\{EMAIL_BACKEND:\?set EMAIL_BACKEND to console or smtp\}$/m,
    "compose should fail with a useful message when EMAIL_BACKEND is missing"
  );
  assert.match(
    exampleEnv,
    /^EMAIL_BACKEND=console$/m,
    "a fresh .env copied from the example should start with console email delivery"
  );
  for (const variable of [
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USE_TLS",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM_EMAIL"
  ]) {
    assert.match(
      exampleEnv,
      new RegExp(`^# ${variable}=`, "m"),
      `${variable} should be documented for SMTP deployments`
    );
  }
});
