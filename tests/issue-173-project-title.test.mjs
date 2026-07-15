import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../app/src/styles.css", import.meta.url), "utf8");

test("project title wraps only between words at constrained widths", () => {
  assert.match(
    source,
    /<Link to="\/about-project" className="project-title [^"]*">\{project\?\.name \?\? "Эпоха Катастроф"\}<\/Link>/,
  );
  assert.match(styles, /\.project-title\s*{[\s\S]*overflow-wrap:\s*normal;[\s\S]*word-break:\s*normal;/);
});
