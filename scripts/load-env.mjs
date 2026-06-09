import fs from "node:fs";
import path from "node:path";

/**
 * Parse the contents of a `.env` file into key/value pairs.
 *
 * Supported syntax:
 *   - `KEY=value` and `export KEY=value`
 *   - blank lines and `#` comment lines are ignored
 *   - surrounding single or double quotes are stripped from the value
 *   - inline comments after an unquoted value are ignored
 *
 * @param {string} content Raw file contents.
 * @returns {Record<string, string>} Parsed environment variables.
 */
export function parseEnv(content) {
  const result = {};

  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (line.length === 0 || line.startsWith("#")) {
      continue;
    }

    const withoutExport = line.startsWith("export ")
      ? line.slice("export ".length).trimStart()
      : line;

    const separatorIndex = withoutExport.indexOf("=");
    if (separatorIndex === -1) {
      continue;
    }

    const key = withoutExport.slice(0, separatorIndex).trim();
    if (key.length === 0) {
      continue;
    }

    let value = withoutExport.slice(separatorIndex + 1).trim();

    const quote = value[0];
    if ((quote === '"' || quote === "'") && value.endsWith(quote) && value.length >= 2) {
      value = value.slice(1, -1);
    } else {
      const commentIndex = value.indexOf(" #");
      if (commentIndex !== -1) {
        value = value.slice(0, commentIndex).trim();
      }
    }

    result[key] = value;
  }

  return result;
}

/**
 * Load a `.env` file from `rootPath` and merge it into `env`.
 *
 * Existing values already present in `env` take precedence, mirroring the
 * behaviour of popular dotenv loaders, so explicit environment variables are
 * never overwritten by the file.
 *
 * @param {string} rootPath Directory that may contain a `.env` file.
 * @param {Record<string, string | undefined>} [env] Target environment (defaults to `process.env`).
 * @returns {Record<string, string>} The variables that were applied from the file.
 */
export function loadEnv(rootPath, env = process.env) {
  const envPath = path.join(rootPath, ".env");
  if (!fs.existsSync(envPath)) {
    return {};
  }

  const parsed = parseEnv(fs.readFileSync(envPath, "utf8"));
  const applied = {};

  for (const [key, value] of Object.entries(parsed)) {
    if (env[key] === undefined) {
      env[key] = value;
      applied[key] = value;
    }
  }

  return applied;
}
