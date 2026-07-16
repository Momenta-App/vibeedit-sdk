import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createExample } from "../src/index.js";

test("Node CLI reports the package version", () => {
  const result = spawnSync(process.execPath, ["bin/vibeedit.js", "--version"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), "vibeedit 0.1.0-beta.2");
});

test("Node CLI doctor probes Python with its supported version flag", () => {
  const result = spawnSync(process.execPath, ["bin/vibeedit.js", "doctor", "--json"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  const payload = JSON.parse(result.stdout);
  const commands = payload.capabilities.commands;
  assert.ok([commands.python3, commands.python].some((command) => command.available && command.version.startsWith("Python ")));
  assert.match(payload.readiness.meaning, /Core/);
  assert.equal(typeof payload.capabilities.htmlMotion.browserInstalled, "boolean");
});

test("Node CLI validates the canonical fixture", () => {
  const result = spawnSync(process.execPath, ["bin/vibeedit.js", "validate", "schema/fixtures/minimal.json", "--json"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).schemaVersion, "1.0.0");
});

test("Node CLI searches stable catalog IDs", () => {
  const result = spawnSync(process.execPath, ["bin/vibeedit.js", "catalog", "search", "procedural", "--json"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.ok(JSON.parse(result.stdout).some((item) => item.id === "vibeedit://sfx/impact-procedural"));
});

test("Node CLI offers compact bounded catalog results", () => {
  const result = spawnSync(process.execPath, ["bin/vibeedit.js", "catalog", "search", "text", "--compact", "--limit", "2", "--json"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.length, 2);
  assert.deepEqual(Object.keys(payload[0]).sort(), ["category", "description", "id", "name", "preview"]);
});

test("Node CLI explains examples and keeps catalog opening in the background", () => {
  const examples = spawnSync(process.execPath, ["bin/vibeedit.js", "examples", "list", "--details", "--json"], { encoding: "utf8" });
  assert.equal(examples.status, 0, examples.stderr);
  assert.ok(JSON.parse(examples.stdout).some((item) => item.id === "basic-generated" && item.recommended));
  const catalog = spawnSync(process.execPath, ["bin/vibeedit.js", "catalog", "open", "--json"], { encoding: "utf8" });
  assert.equal(catalog.status, 0, catalog.stderr);
  assert.equal(JSON.parse(catalog.stdout).opened, false);
});

test("Node CLI honors the examples output directory", () => {
  const root = mkdtempSync(join(tmpdir(), "vibeedit-cli-example-"));
  try {
    const result = spawnSync(process.execPath, ["bin/vibeedit.js", "examples", "create", "basic-generated", "--output", root, "--json"], { encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).path, join(root, "basic-generated"));
  } finally {
    rmSync(root, { recursive: true });
  }
});

test("Node CLI returns actionable missing-file errors", () => {
  const result = spawnSync(process.execPath, ["bin/vibeedit.js", "validate", "missing.json", "--json"], { encoding: "utf8" });
  assert.equal(result.status, 1);
  assert.match(JSON.parse(result.stdout).error, /vibeedit init composition\.json/);
});

test("Node CLI help gives an agent a starting workflow", () => {
  const result = spawnSync(process.execPath, ["bin/vibeedit.js", "--help"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /examples list --details/);
  assert.match(result.stdout, /catalog search kinetic --compact/);
});

test("Node CLI doctor defaults to a concise human summary", () => {
  const result = spawnSync(process.execPath, ["bin/vibeedit.js", "doctor"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /^VibeEdit doctor:/);
  assert.match(result.stdout, /doctor --json/);
});

test("JavaScript API creates a packaged example without overwriting", () => {
  const root = mkdtempSync(join(tmpdir(), "vibeedit-example-"));
  try {
    const target = createExample("basic-generated", root);
    assert.ok(target.endsWith("basic-generated"));
    assert.throws(() => createExample("basic-generated", root), /already exists/);
  } finally {
    rmSync(root, { recursive: true });
  }
});
