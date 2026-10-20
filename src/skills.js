import { createHash, randomUUID } from "node:crypto";
import { closeSync, cpSync, existsSync, fsyncSync, lstatSync, mkdirSync, openSync, readFileSync, readdirSync, realpathSync, renameSync, rmSync, rmdirSync, unlinkSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { dataPath } from "./data.js";

const harnessDirectories = { agents: ".agents/skills", codex: ".codex/skills", claude: ".claude/skills", opencode: ".opencode/skills" };
const trackerName = ".vibeedit-install.json";

export function listSkills() {
  return ["index.json", "owned.json"].flatMap(name => JSON.parse(readFileSync(dataPath(`skills/${name}`), "utf8")).skills);
}

export function installSkill(id, options) { return operate(id, options, "install"); }
export function checkSkill(id, options) { return operate(id, options, "check"); }
export function updateSkill(id, options) { return operate(id, options, "update"); }
export function removeSkill(id, options) { return operate(id, options, "remove"); }

function operate(id, { harness, scope = "project", cwd = process.cwd() }, action) {
  const skill = requireSkill(id, harness);
  const destination = skillDestination(skill, harness, scope, cwd);
  return withLock(destination, () => {
    recover(destination, skill, harness);
    const record = readTracker(destination, skill, harness);
    const modified = record !== null && treeChecksum(destination, new Set([trackerName])) !== record.checksum;
    const result = { id: skill.id, destination };
    if (action === "check") return { ...result, action: "check", installed: record !== null, ...(record ? { modified, version: record.version, currentVersion: skill.version } : {}) };
    if (modified) throw new Error(`refusing to ${action} a user-modified skill: ${destination}`);
    if (existsSync(destination) && record === null) throw new Error(`refusing to overwrite unmanaged existing skill: ${destination}`);
    if (action === "remove") {
      if (record === null) return { ...result, action: "remove", removed: false };
      transaction(destination, skill, harness, record, null);
      return { ...result, action: "remove", removed: true };
    }
    const source = dataPath(`skills/${skill.path}`);
    if (existsSync(join(source, trackerName)) || treeChecksum(source) !== skill.checksum) throw new Error(`bundled skill checksum mismatch: ${skill.id}`);
    if (action === "install" && record !== null) {
      if (record.version === skill.version && record.checksum === skill.checksum) return { ...result, action: "reused", version: skill.version };
      throw new Error(`existing managed skill requires update: ${destination}`);
    }
    transaction(destination, skill, harness, record, source);
    return { ...result, action: record ? "updated" : "installed", version: skill.version };
  });
}

function operationPaths(destination) {
  return Object.fromEntries(Object.entries({ stage: "stage", previous: "previous", journal: "operation.json", lock: "lock" }).map(([key, suffix]) => [key, join(dirname(destination), `.${destination.split(/[\\/]/).at(-1)}.vibeedit-${suffix}`)]));
}

function transaction(destination, skill, harness, previous, source) {
  const paths = operationPaths(destination);
  const operation = { schemaVersion: "vibeedit.skill-operation.v1", id: skill.id, harness, operationId: randomUUID().replaceAll("-", ""), action: source ? "replace" : "remove", previousChecksum: previous?.checksum ?? null, newChecksum: source ? skill.checksum : null, phase: "preparing" };
  atomicJson(paths.journal, operation);
  if (source !== null) {
    mkdirSync(paths.stage);
    atomicJson(join(paths.stage, trackerName), { schemaVersion: 1, id: skill.id, version: skill.version, harness, checksum: skill.checksum, operationId: operation.operationId });
    cpSync(source, paths.stage, { recursive: true, dereference: false, filter: path => !path.split(/[\\/]/).includes("__pycache__") && !path.endsWith(".pyc") });
    if (treeChecksum(paths.stage, new Set([trackerName])) !== operation.newChecksum) throw new Error("staged skill checksum mismatch; previous installation preserved");
  }
  operation.phase = "ready";
  atomicJson(paths.journal, operation);
  recover(destination, skill, harness);
}

function recover(destination, skill, harness) {
  const paths = operationPaths(destination);
  Object.values(paths).forEach(noSymlink);
  if (!existsSync(paths.journal)) {
    if (existsSync(paths.stage) || existsSync(paths.previous)) throw new Error(`unowned skill recovery artifacts; preserve and inspect: ${destination}`);
    return;
  }
  const operation = JSON.parse(readFileSync(paths.journal, "utf8"));
  if (operation.schemaVersion !== "vibeedit.skill-operation.v1" || operation.id !== skill.id || operation.harness !== harness || !["replace", "remove"].includes(operation.action) || !["preparing", "ready", "committed"].includes(operation.phase) || typeof operation.operationId !== "string" || !/^[a-f0-9]{32}$/.test(operation.operationId)) throw new Error("invalid skill operation journal; preserve and inspect");
  for (const key of ["previousChecksum", "newChecksum"]) {
    if (operation[key] !== null && (typeof operation[key] !== "string" || !/^[a-f0-9]{64}$/.test(operation[key]))) throw new Error("invalid skill operation checksum; preserve and inspect");
  }
  const old = operation.previousChecksum;
  const next = operation.newChecksum;
  if ((operation.action === "replace") !== (next !== null)) throw new Error("invalid skill operation action; preserve and inspect");
  const matches = (path, checksum, current = false) => {
    if (!existsSync(path) || checksum === null) return false;
    const record = readTracker(path, skill, harness);
    return record !== null && record.checksum === checksum && (!current || record.operationId === operation.operationId) && treeChecksum(path, new Set([trackerName])) === checksum;
  };
  if (existsSync(paths.previous) && !matches(paths.previous, old)) throw new Error("user-modified skill backup; preserve and inspect");
  if (existsSync(destination) && !(matches(destination, next, true) || (!existsSync(paths.previous) && matches(destination, old)))) throw new Error("conflicting or user-modified skill during recovery; preserve and inspect");
  const ready = matches(paths.stage, next, true);
  if (next !== null && !matches(destination, next, true) && !ready) {
    // Retain partial copies for inspection; an incomplete stage never destroys the old install.
    if (existsSync(paths.stage)) {
      const quarantine = `${paths.stage}.aborted-${operation.operationId}`;
      noSymlink(quarantine);
      if (existsSync(quarantine)) throw new Error("skill quarantine already exists; preserve and inspect");
      renameSync(paths.stage, quarantine);
    }
    if (existsSync(paths.previous) && !existsSync(destination)) renameSync(paths.previous, destination);
    if (old !== null && !matches(destination, old)) throw new Error("previous skill missing; preserve recovery journal");
    unlinkSync(paths.journal);
    return;
  }
  if (!matches(destination, next, true) && operation.phase !== "committed") {
    if (existsSync(destination)) renameSync(destination, paths.previous);
    if (next !== null) renameSync(paths.stage, destination);
  }
  if (next !== null && !matches(destination, next, true)) throw new Error("committed skill is missing; preserve recovery journal");
  if (next === null && existsSync(destination)) throw new Error("removed skill still exists; preserve recovery journal");
  operation.phase = "committed";
  atomicJson(paths.journal, operation);
  if (existsSync(paths.stage)) {
    if (!matches(paths.stage, next, true)) throw new Error("modified redundant skill stage; preserve and inspect");
    rmSync(paths.stage, { recursive: true });
  }
  if (existsSync(paths.previous)) rmSync(paths.previous, { recursive: true });
  unlinkSync(paths.journal);
}

function withLock(destination, run) {
  mkdirSync(dirname(destination), { recursive: true });
  const lock = operationPaths(destination).lock;
  noSymlink(lock);
  try { mkdirSync(lock); }
  catch (error) {
    if (error.code !== "EEXIST") throw error;
    noSymlink(join(lock, "owner.json"));
    if (!existsSync(join(lock, "owner.json"))) throw new Error(`incomplete skill lock; preserve and inspect: ${lock}`);
    const owner = JSON.parse(readFileSync(join(lock, "owner.json"), "utf8"));
    if (owner.schemaVersion !== 1 || typeof owner.nonce !== "string" || !/^[a-f0-9]{32}$/.test(owner.nonce) || !Number.isSafeInteger(owner.pid) || owner.pid <= 0 || owner.pid >= 2 ** 31 || alive(owner.pid)) throw new Error(`skill operation locked; preserve active or unknown owner: ${lock}`);
    const reclaim = `${lock}.reclaim`;
    noSymlink(reclaim);
    try { mkdirSync(reclaim); }
    catch (error) {
      if (error.code !== "EEXIST") throw error;
      throw new Error(`skill lock recovery already in progress: ${reclaim}`);
    }
    try {
      if (JSON.stringify(JSON.parse(readFileSync(join(lock, "owner.json"), "utf8"))) !== JSON.stringify(owner) || alive(owner.pid)) throw new Error("skill lock owner changed during recovery");
      rmSync(lock, { recursive: true });
      mkdirSync(lock);
    } finally { rmdirSync(reclaim); }
  }
  const nonce = randomUUID().replaceAll("-", "");
  atomicJson(join(lock, "owner.json"), { schemaVersion: 1, pid: process.pid, nonce });
  try { return run(); }
  finally {
    noSymlink(lock);
    noSymlink(join(lock, "owner.json"));
    if (JSON.parse(readFileSync(join(lock, "owner.json"), "utf8")).nonce !== nonce) throw new Error("skill lock ownership changed; preserve and inspect");
    rmSync(lock, { recursive: true });
  }
}

function alive(pid) {
  try { process.kill(pid, 0); return true; }
  catch (error) { return error.code !== "ESRCH"; }
}

function atomicJson(path, value) {
  noSymlink(path);
  const temporary = `${path}.tmp-${randomUUID().replaceAll("-", "")}`;
  const descriptor = openSync(temporary, "wx");
  try { writeFileSync(descriptor, `${JSON.stringify(value, null, 2)}\n`); fsyncSync(descriptor); }
  finally { closeSync(descriptor); }
  renameSync(temporary, path);
  if (process.platform === "win32") return;
  const directory = openSync(dirname(path), "r");
  try { fsyncSync(directory); }
  finally { closeSync(directory); }
}

export function treeChecksum(root, excluded = new Set()) {
  noSymlink(root);
  const files = [];
  const visit = (directory, prefix = "") => {
    for (const name of readdirSync(directory)) {
      const path = join(directory, name);
      const relative = prefix ? `${prefix}/${name}` : name;
      const info = lstatSync(path);
      if (info.isSymbolicLink() || (!info.isDirectory() && !info.isFile())) throw new Error(`refusing skill symlink or special file: ${path}`);
      if (info.isDirectory() && name !== "__pycache__") visit(path, relative);
      if (info.isFile() && !name.endsWith(".pyc") && !excluded.has(relative)) files.push(relative);
    }
  };
  visit(root);
  const hash = createHash("sha256");
  for (const relative of files.sort((a, b) => Buffer.compare(Buffer.from(a), Buffer.from(b)))) hash.update(relative).update("\0").update(readFileSync(join(root, relative))).update("\0");
  return hash.digest("hex");
}

function requireSkill(id, harness) {
  const skill = listSkills().find(item => item.id === id || item.name === id);
  if (!skill) throw new Error(`unknown skill: ${id}`);
  if (!harnessDirectories[harness] || !skill.harnesses.includes(harness)) throw new Error(`skill ${skill.id} does not support harness ${harness}`);
  if (typeof skill.name !== "string" || ["", ".", ".."].includes(skill.name) || /[\\/]/.test(skill.name)) throw new Error("unsafe skill name");
  return skill;
}

function skillDestination(skill, harness, scope, cwd) {
  if (!["project", "user"].includes(scope)) throw new Error("skill scope must be project or user");
  const requested = resolve(scope === "user" ? homedir() : cwd);
  // Resolve an existing explicit root, while rejecting symlinks below that root.
  const base = canonicalRoot(requested);
  const destination = join(base, harnessDirectories[harness], skill.name);
  [dirname(dirname(destination)), dirname(destination), destination].forEach(noSymlink);
  return destination;
}

function canonicalRoot(path) {
  if (existsSync(path)) return realpathSync(path);
  return join(canonicalRoot(dirname(path)), path.split(/[\\/]/).at(-1));
}

function noSymlink(path) {
  try { if (lstatSync(path).isSymbolicLink()) throw new Error(`refusing skill symlink: ${path}`); }
  catch (error) { if (error.code !== "ENOENT") throw error; }
}

function readTracker(destination, skill, harness) {
  noSymlink(destination);
  const path = join(destination, trackerName);
  noSymlink(path);
  if (!existsSync(path)) return null;
  const record = JSON.parse(readFileSync(path, "utf8"));
  if (record.schemaVersion !== 1 || record.id !== skill.id || record.harness !== harness || typeof record.version !== "string" || typeof record.checksum !== "string" || !/^[a-f0-9]{64}$/.test(record.checksum)) throw new Error(`invalid skill install tracker; preserve and inspect: ${destination}`);
  return record;
}
