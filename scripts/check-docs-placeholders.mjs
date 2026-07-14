import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

const root = process.cwd();
const denied = ["TODO fake", "dummy data", "lorem ipsum"];

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      if ([".git", "node_modules", ".next", ".venv"].includes(entry.name)) continue;
      yield* walk(path);
    } else {
      yield path;
    }
  }
}

let failed = false;

for await (const file of walk(root)) {
  if (!file.endsWith(".md") && !file.endsWith(".yaml") && !file.endsWith(".yml")) continue;
  const content = await readFile(file, "utf8");
  for (const phrase of denied) {
    if (content.toLowerCase().includes(phrase.toLowerCase())) {
      console.error(`Denied placeholder phrase "${phrase}" found in ${file}`);
      failed = true;
    }
  }
}

if (failed) process.exit(1);
