import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";

const nginxConfig = fs.readFileSync("docker/nginx.conf", "utf8");

function extractBlock(text, directivePattern) {
  const match = directivePattern.exec(text);
  assert.ok(match, `missing block matching ${directivePattern}`);

  const start = text.indexOf("{", match.index);
  assert.notEqual(start, -1, `missing opening brace for ${match[0]}`);

  let depth = 0;
  for (let index = start; index < text.length; index += 1) {
    if (text[index] === "{") {
      depth += 1;
    } else if (text[index] === "}") {
      depth -= 1;
      if (depth === 0) {
        return text.slice(start + 1, index);
      }
    }
  }

  assert.fail(`missing closing brace for ${match[0]}`);
}

function topLevelDirectives(block) {
  let depth = 0;
  let output = "";

  for (const character of block) {
    if (character === "{") {
      depth += 1;
      continue;
    }

    if (character === "}") {
      depth -= 1;
      continue;
    }

    if (depth === 0) {
      output += character;
    }
  }

  return output;
}

function assertAntiFramingHeaders(block, context) {
  assert.match(
    block,
    /add_header\s+Content-Security-Policy\s+"frame-ancestors 'none'"\s+always;/,
    `${context} must deny framing with CSP frame-ancestors on every response`
  );
  assert.match(
    block,
    /add_header\s+X-Frame-Options\s+"DENY"\s+always;/,
    `${context} must deny framing for legacy browsers on every response`
  );
}

test("nginx denies framing on SPA and proxied API responses", () => {
  const serverBlock = extractBlock(nginxConfig, /\bserver\s*\{/);

  assertAntiFramingHeaders(topLevelDirectives(serverBlock), "server");
});

test("nginx preserves anti-framing headers in locations with custom headers", () => {
  const assetsBlock = extractBlock(nginxConfig, /location\s+\/assets\/\s*\{/);

  assertAntiFramingHeaders(topLevelDirectives(assetsBlock), "assets location");
  assert.match(
    assetsBlock,
    /add_header\s+Cache-Control\s+"public, immutable"\s+always;/,
    "asset cache header should also use always so error responses keep explicit header behavior"
  );
});
