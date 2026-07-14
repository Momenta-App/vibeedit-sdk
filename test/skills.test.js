import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";
import { checkSkill, installSkill, listSkills, removeSkill, updateSkill } from "../src/index.js";

test("skill install tracks versions and protects user edits", async () => {
  const { mkdtemp } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const cwd = await mkdtemp(join(tmpdir(), "vibeedit-skill-"));
  const options = { harness: "codex", scope: "project", cwd };
  const installed = installSkill("vibeedit-workspace", options);
  assert.equal(checkSkill("vibeedit-workspace", options).modified, false);
  await writeFile(join(installed.destination, "SKILL.md"), "user edit\n");
  assert.equal(checkSkill("vibeedit-workspace", options).modified, true);
  assert.throws(() => updateSkill("vibeedit-workspace", options), /user-modified/);
  assert.throws(() => removeSkill("vibeedit-workspace", options), /user-modified/);
});

test("all release-safe skills install into every supported harness", async () => {
  const { mkdtemp } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  assert.equal(listSkills().length, 44);
  for (const [index, skill] of listSkills().entries()) {
    const harness = ["agents", "codex", "claude", "opencode"][index % 4];
    const cwd = await mkdtemp(join(tmpdir(), "vibeedit-skill-matrix-"));
    const options = { harness, scope: "project", cwd };
    installSkill(skill.id, options);
    assert.equal(checkSkill(skill.name, options).modified, false);
    assert.equal(removeSkill(skill.id, options).removed, true);
  }
});
