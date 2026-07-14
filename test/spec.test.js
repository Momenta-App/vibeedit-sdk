import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { canonicalJson, validateComposition } from "../src/index.js";

for (const name of ["minimal", "mixed"]) {
  test(`${name} fixture validates and canonicalizes`, async () => {
    const value = JSON.parse(await readFile(new URL(`../schema/fixtures/${name}.json`, import.meta.url), "utf8"));
    validateComposition(value);
    assert.equal(canonicalJson(value), canonicalJson(JSON.parse(canonicalJson(value))));
  });
}

test("schema rejects unknown root fields", async () => {
  const value = JSON.parse(await readFile(new URL("../schema/fixtures/minimal.json", import.meta.url), "utf8"));
  value.unknown = true;
  assert.throws(() => validateComposition(value), /additional properties/i);
});
