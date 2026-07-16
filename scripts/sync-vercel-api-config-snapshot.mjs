import { createHash } from "node:crypto";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
} from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("..", import.meta.url));
const sourceRoot = join(repoRoot, "configs");
const snapshotRoot = join(repoRoot, "services", "api-vercel", "configs");
const registryDirs = ["connectors", "tools", "workflows"];
const checkOnly = process.argv.includes("--check");

if (checkOnly) {
  const diffs = findSnapshotDiffs();
  if (diffs.length > 0) {
    console.error("Vercel API config snapshot is out of sync:");
    for (const diff of diffs) {
      console.error(`- ${diff}`);
    }
    process.exit(1);
  }

  console.log("Vercel API config snapshot is in sync.");
} else {
  rmSync(snapshotRoot, { force: true, recursive: true });
  mkdirSync(snapshotRoot, { recursive: true });

  for (const registryDir of registryDirs) {
    cpSync(join(sourceRoot, registryDir), join(snapshotRoot, registryDir), {
      recursive: true,
    });
  }

  console.log("Synced Vercel API config snapshot.");
}

function findSnapshotDiffs() {
  const diffs = [];

  for (const registryDir of registryDirs) {
    const sourceDir = join(sourceRoot, registryDir);
    const snapshotDir = join(snapshotRoot, registryDir);
    const sourceFiles = listFiles(sourceDir);
    const snapshotFiles = listFiles(snapshotDir);
    const relativePaths = new Set([
      ...sourceFiles.map((file) => relative(sourceDir, file)),
      ...snapshotFiles.map((file) => relative(snapshotDir, file)),
    ]);

    for (const relativePath of [...relativePaths].sort()) {
      const sourcePath = join(sourceDir, relativePath);
      const snapshotPath = join(snapshotDir, relativePath);

      if (!existsSync(sourcePath)) {
        diffs.push(`extra snapshot file ${registryDir}/${relativePath}`);
        continue;
      }

      if (!existsSync(snapshotPath)) {
        diffs.push(`missing snapshot file ${registryDir}/${relativePath}`);
        continue;
      }

      if (hashFile(sourcePath) !== hashFile(snapshotPath)) {
        diffs.push(`changed snapshot file ${registryDir}/${relativePath}`);
      }
    }
  }

  return diffs;
}

function listFiles(directory) {
  if (!existsSync(directory)) {
    return [];
  }

  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      return listFiles(path);
    }
    if (entry.isFile()) {
      return [path];
    }
    return [];
  });
}

function hashFile(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}
