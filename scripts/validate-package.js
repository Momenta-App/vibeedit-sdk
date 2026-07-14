import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import { treeChecksum, validateComposition } from "../src/index.js";

const root = new URL("..", import.meta.url);
const read = (path) => readFileSync(new URL(path, root), "utf8");
const packageJson = JSON.parse(read("package.json"));
assert.equal(packageJson.license, "SEE LICENSE IN LICENSE.md");
assert.equal(packageJson.version, "0.1.0");
assert.match(read("pyproject.toml"), /version = "0\.1\.0"/);
assert.match(read("LICENSE.md"), /Commercial use requires a separate\s+commercial\s+license/);

const catalog = JSON.parse(read("catalog/catalog.json"));
const catalogSchema = JSON.parse(read("catalog/catalog.schema.json"));
const validateCatalog = new Ajv2020({ strict: false, allErrors: true }).compile(catalogSchema);
assert.ok(validateCatalog(catalog), JSON.stringify(validateCatalog.errors));
assert.equal(new Set(catalog.items.map((item) => item.id)).size, catalog.items.length);
assert.ok(catalog.items.every((item) => item.validation.length && item.validation.every((test) => test.status !== "pending")));
for (const item of catalog.items) new Function(item.examples.javascript);
for (const item of catalog.items) assert.ok(statSync(new URL(item.provenance.implementation, root)).isFile(), `missing implementation for ${item.id}`);
for (const item of catalog.items.filter((item) => item.preview.status === "verified")) assert.ok(statSync(new URL(`catalog/${item.preview.uri}`, root)).size > 0);

for (const directory of ["schema/fixtures", ...readdirSync(new URL("examples/", root), { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => `examples/${entry.name}`)]) {
  for (const name of readdirSync(new URL(directory, root)).filter((name) => directory === "schema/fixtures" ? name.endsWith(".json") : name === "composition.json")) validateComposition(JSON.parse(read(`${directory}/${name}`)));
}

const siteData = read("site/catalog-data.js");
assert.match(siteData, /^globalThis\.VIBEEDIT_CATALOG = /);
assert.match(read("site/index.html"), /copy-python/);
assert.match(read("site/index.html"), /copy-javascript/);
assert.match(read("site/app.js"), /item\.examples\.python/);
assert.match(read("site/app.js"), /item\.examples\.javascript/);
assert.deepEqual(
  JSON.parse(siteData.slice("globalThis.VIBEEDIT_CATALOG = ".length, -2)),
  catalog,
  "catalog site data is stale; run npm run catalog:build",
);
const skills = JSON.parse(read("skills/index.json"));
for (const skill of skills.skills) {
  assert.equal(skill.source?.sha256, skill.checksum, `canonical source differs from packaged skill ${skill.id}`);
  assert.equal(skill.checksum, treeChecksum(fileURLToPath(new URL(`skills/${skill.path}`, root))), `stale checksum for ${skill.id}`);
}
assert.ok(!skills.skills.some((skill) => skill.name === "production-basics"), "package-only replacement skill must not return");

const assets = JSON.parse(read("catalog/assets.json"));
for (const asset of assets.assets) {
  const path = new URL(asset.path, root);
  assert.ok(statSync(path).size === asset.bytes && asset.decodable && asset.redistribution === "verified");
  if (asset.category === "procedural-sfx") assert.equal(typeof asset.loudnessLufs, "number");
}

const forbidden = [/\/Users\/[A-Za-z0-9._-]+\//, /AKIA[0-9A-Z]{16}/, /service[_-]?role[_-]?(key|secret)/i, /BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY/];
const scanRoots = ["python", "src", "bin", "catalog", "schema", "skills", "site", "examples", "runtime-models", "docs", "scripts"];
for (const directory of scanRoots) scan(new URL(`${directory}/`, root));

console.log(JSON.stringify({ ok: true, version: packageJson.version, catalogItems: catalog.items.length, skills: skills.skills.length, assets: assets.assets.length }));

function scan(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (["node_modules", ".venv", "__pycache__", ".pytest_cache"].includes(entry.name)) continue;
    const path = new URL(`${entry.name}${entry.isDirectory() ? "/" : ""}`, directory);
    if (entry.isDirectory()) { scan(path); continue; }
    if (!/\.(js|ts|py|json|md|css|html|toml)$/.test(entry.name)) continue;
    const value = readFileSync(path, "utf8");
    for (const pattern of forbidden) assert.ok(!pattern.test(value), `${relative(new URL(".", root).pathname, path.pathname)} matches forbidden ${pattern}`);
  }
}
