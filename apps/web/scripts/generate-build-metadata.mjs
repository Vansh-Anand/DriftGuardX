import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const webDir = resolve(scriptDir, "..");
const repoDir = resolve(webDir, "../..");
const pyproject = readFileSync(resolve(repoDir, "pyproject.toml"), "utf8");
const packageJson = JSON.parse(readFileSync(resolve(webDir, "package.json"), "utf8"));
const match = pyproject.match(/^version\s*=\s*"([^"]+)"/m);

if (!match) throw new Error("Project version is missing from pyproject.toml");
const canonicalVersion = match[1].replace(/rc(\d+)$/, "-rc.$1");
if (packageJson.version !== canonicalVersion) {
  throw new Error(`Web version ${packageJson.version} != canonical ${canonicalVersion}`);
}

function git(...args) {
  try {
    return execFileSync("git", args, { cwd: repoDir, encoding: "utf8" }).trim();
  } catch {
    return "unknown";
  }
}

const commit = process.env.GITHUB_SHA || git("rev-parse", "HEAD");
const commitTime = process.env.SOURCE_DATE_EPOCH
  ? new Date(Number(process.env.SOURCE_DATE_EPOCH) * 1000).toISOString()
  : git("show", "-s", "--format=%cI", commit);
const metadata = {
  schema_version: "1.0",
  version: canonicalVersion,
  commit,
  commit_time: commitTime,
  verification: process.env.DGX_VERIFICATION_STATUS || "unverified-local-build",
  verification_source: process.env.GITHUB_RUN_ID ? `github-actions:${process.env.GITHUB_RUN_ID}` : "local",
};

const target = resolve(webDir, "src/generated/build-metadata.json");
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, `${JSON.stringify(metadata, null, 2)}\n`, "utf8");
console.log(`Generated ${target} for ${canonicalVersion} (${commit.slice(0, 12)})`);
