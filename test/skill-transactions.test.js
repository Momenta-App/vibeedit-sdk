import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { checkSkill, installSkill, removeSkill, updateSkill } from "../src/skills.js";

const child = (cwd, script) => spawnSync(process.execPath, ["--input-type=module", "-e", script, cwd], { cwd: new URL("..", import.meta.url), encoding: "utf8", timeout: 20000 });

test("real child crash after old rename recovers an update", () => {
  const cwd = mkdtempSync(join(tmpdir(), "vibeedit-skill-crash-"));
  const options = { harness: "codex", cwd };
  const installed = installSkill("vibeedit-workspace", options);
  const result = child(cwd, `
import fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";
const original = fs.renameSync;
fs.renameSync = (source, destination) => {
  original(source, destination);
  if (destination.endsWith(".vibeedit-previous")) process.exit(72);
};
syncBuiltinESMExports();
const { updateSkill } = await import("./src/skills.js");
updateSkill("vibeedit-workspace", { harness: "codex", cwd:process.argv[1] });
`);
  assert.equal(result.status, 72, result.stderr);
  assert.equal(checkSkill("vibeedit-workspace", options).modified, false);
  assert.deepEqual(readdirSync(dirname(installed.destination)), ["vibeedit-workspace"]);
  assert.equal(installSkill("vibeedit-workspace", options).action, "reused");
});

test("interrupted partial copy is retained while old install remains usable", () => {
  const cwd = mkdtempSync(join(tmpdir(), "vibeedit-skill-partial-"));
  const options = { harness: "codex", cwd };
  const installed = installSkill("vibeedit-workspace", options);
  const result = child(cwd, `
import fs from "node:fs";
import { join } from "node:path";
import { syncBuiltinESMExports } from "node:module";
const original = fs.cpSync;
fs.cpSync = (source, destination, options) => {
  original(source, destination, options);
  fs.writeFileSync(join(destination, "SKILL.md"), "interrupted partial copy");
  process.exit(73);
};
syncBuiltinESMExports();
const { updateSkill } = await import("./src/skills.js");
updateSkill("vibeedit-workspace", { harness: "codex", cwd:process.argv[1] });
`);
  assert.equal(result.status, 73, result.stderr);
  assert.equal(checkSkill("vibeedit-workspace", options).modified, false);
  const quarantine = readdirSync(dirname(installed.destination)).find(name => name.includes("vibeedit-stage.aborted-"));
  assert.ok(quarantine);
  assert.equal(readFileSync(join(dirname(installed.destination), quarantine, "SKILL.md"), "utf8"), "interrupted partial copy");
  assert.equal(updateSkill("vibeedit-workspace", options).action, "updated");
});

test("symlinked installed content cannot be removed or overwritten", () => {
  const cwd = mkdtempSync(join(tmpdir(), "vibeedit-skill-link-"));
  const options = { harness: "codex", cwd };
  const installed = installSkill("vibeedit-workspace", options);
  const outside = join(cwd, "outside.txt");
  writeFileSync(outside, "preserve user data");
  symlinkSync(outside, join(installed.destination, "escape.txt"));
  assert.throws(() => removeSkill("vibeedit-workspace", options), /symlink/);
  assert.throws(() => updateSkill("vibeedit-workspace", options), /symlink/);
  assert.equal(readFileSync(outside, "utf8"), "preserve user data");
});
