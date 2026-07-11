import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const styles = await readFile(new URL("../app/src/styles.css", import.meta.url), "utf8");

test("responsive tables preserve complete words in headers and long values", () => {
  assert.match(
    styles,
    /\.responsive-table\s+th\s*\{[^}]*white-space:\s*nowrap[^}]*overflow-wrap:\s*normal[^}]*\}/s,
  );
  assert.match(
    styles,
    /\.responsive-table\s+td\s*\{[^}]*overflow-wrap:\s*break-word[^}]*\}/s,
  );
});
