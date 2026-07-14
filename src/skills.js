import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { dataPath } from "./data.js";

const harnessDirectories = { agents: ".agents/skills", codex: ".codex/skills", claude: ".claude/skills", opencode: ".opencode/skills" };

export function listSkills() {
  return JSON.parse(readFileSync(dataPath("skills/index.json"), "utf8")).skills;
}

export function installSkill(id, { harness, scope = "project", cwd = process.cwd() }) {
  const skill = requireSkill(id);
  requireHarness(skill, harness);
  const source = dataPath(`skills/${skill.path}`);
  const destination = skillDestination(skill, harness, scope, cwd);
  if (existsSync(destination)) throw new Error(`refusing to overwrite existing skill: ${destination}`);
  mkdirSync(destination, { recursive: true });
  cpSync(source, destination, { recursive: true });
  writeTracker(destination, skill, harness, treeChecksum(source));
  return { action: "installed", id: skill.id, version: skill.version, destination };
}

export function checkSkill(id, options) {
  const skill = requireSkill(id);
  const destination = skillDestination(skill, options.harness, options.scope ?? "project", options.cwd ?? process.cwd());
  const tracker = readTracker(destination);
  if (!tracker) return { action: "check", id, installed: false, destination };
  const modified = treeChecksum(destination, new Set([".vibeedit-install.json"])) !== tracker.checksum;
  return { action: "check", id, installed: true, modified, version: tracker.version, currentVersion: skill.version, destination };
}

export function updateSkill(id, options) {
  const status = checkSkill(id, options);
  if (!status.installed) return installSkill(id, options);
  if (status.modified) throw new Error(`refusing to overwrite a user-modified skill: ${status.destination}`);
  const skill = requireSkill(id);
  const source = dataPath(`skills/${skill.path}`);
  rmSync(status.destination, { recursive: true });
  mkdirSync(status.destination, { recursive: true });
  cpSync(source, status.destination, { recursive: true });
  writeTracker(status.destination, skill, options.harness, treeChecksum(source));
  return { action: "updated", id, version: skill.version, destination: status.destination };
}

export function removeSkill(id, options) {
  const status = checkSkill(id, options);
  if (!status.installed) return { action: "remove", id, removed: false, destination: status.destination };
  if (status.modified) throw new Error(`refusing to remove a user-modified skill: ${status.destination}`);
  rmSync(status.destination, { recursive: true });
  return { action: "remove", id, removed: true, destination: status.destination };
}

export function treeChecksum(root, excluded = new Set()) {
  const hash = createHash("sha256");
  const visit = (directory, prefix = "") => {
    for (const name of readdirSync(directory).sort()) {
      if (excluded.has(name)) continue;
      const path = join(directory, name);
      const relative = prefix ? `${prefix}/${name}` : name;
      if (statSync(path).isDirectory()) { visit(path, relative); continue; }
      hash.update(relative).update("\0").update(readFileSync(path)).update("\0");
    }
  };
  visit(root);
  return hash.digest("hex");
}

function requireSkill(id) {
  const skill = listSkills().find((item) => item.id === id || item.name === id);
  if (!skill) throw new Error(`unknown skill: ${id}`);
  return skill;
}

function requireHarness(skill, harness) {
  if (!harnessDirectories[harness] || !skill.harnesses.includes(harness)) throw new Error(`skill ${skill.id} does not support harness ${harness}`);
}

function skillDestination(skill, harness, scope, cwd) {
  requireHarness(skill, harness);
  return join(scope === "user" ? homedir() : cwd, harnessDirectories[harness], skill.name);
}

function readTracker(destination) {
  const path = join(destination, ".vibeedit-install.json");
  return existsSync(path) ? JSON.parse(readFileSync(path, "utf8")) : null;
}

function writeTracker(destination, skill, harness, checksum) {
  writeFileSync(join(destination, ".vibeedit-install.json"), `${JSON.stringify({ schemaVersion: 1, id: skill.id, version: skill.version, harness, checksum }, null, 2)}\n`);
}
