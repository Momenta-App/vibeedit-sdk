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
  assert.equal(result.stdout.trim(), "vibeedit 0.1.0");
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
