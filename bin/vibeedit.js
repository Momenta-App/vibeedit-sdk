#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { platform } from "node:os";
import { join, resolve } from "node:path";
import process from "node:process";
import { catalog, checkSkill, createExample, installSkill, listSkills, removeSkill, searchCatalog, updateSkill, validateComposition } from "../src/index.js";
import { dataPath } from "../src/data.js";

const [command, ...args] = process.argv.slice(2);

if (!command || ["help", "--help", "-h"].includes(command)) {
  console.log(`VibeEdit 0.1.0

Usage: vibeedit <command> [options]

Commands:
  init, setup, doctor, inspect, validate, preview, render, verify, clean, mcp
  catalog list|search|open
  examples list|create
  skills list|install|check|update|remove`);
  process.exit(0);
}

if (["version", "--version", "-V"].includes(command)) {
  console.log("vibeedit 0.1.0");
  process.exit(0);
}

try {
  const result = await route(command, args);
  if (result !== undefined) console.log(jsonOutput(args) ? JSON.stringify(result, null, 2) : format(result));
} catch (error) {
  if (jsonOutput(args)) console.log(JSON.stringify({ ok: false, error: error.message }));
  else console.error(`vibeedit: ${error.message}`);
  process.exitCode = 1;
}

async function route(name, values) {
  if (name === "init") return init(values);
  if (name === "doctor") return doctor();
  if (name === "validate") return validate(values);
  if (name === "inspect") return inspect(values);
  if (name === "catalog") return catalogCommand(values);
  if (name === "examples") return examplesCommand(values);
  if (name === "skills") return skillsCommand(values);
  if (["setup", "preview", "render", "verify", "clean", "mcp"].includes(name)) return python(name, values);
  throw new Error(`unknown command: ${name}`);
}

function init(values) {
  const output = positional(values)[0] ?? "composition.json";
  const width = Number(option(values, "--width") ?? 1920);
  const height = Number(option(values, "--height") ?? 1080);
  const durationFrames = Number(option(values, "--frames") ?? 150);
  const fps = (option(values, "--fps") ?? "30/1").split("/").map(Number);
  const spec = {
    schemaVersion: "1.0.0", kind: "vibeedit.composition", id: option(values, "--id") ?? "composition",
    canvas: { width, height, frameRate: { numerator: fps[0], denominator: fps[1] ?? 1 }, audioSampleRate: 48000 },
    durationFrames, sources: [], timeline: { tracks: [] }, artifacts: { masks: [], tracking: [], analysis: [] },
    render: { backend: "ffmpeg", output: { uri: "output.mp4", container: "mp4", videoCodec: "h264", audioCodec: "aac", pixelFormat: "yuv420p" }, deterministic: true },
    provenance: { generator: "vibeedit-node", generatorVersion: "0.1.0", createdAt: new Date().toISOString(), schemaSource: "schema/composition.schema.json" },
  };
  validateComposition(spec);
  writeFileSync(output, `${JSON.stringify(spec, null, 2)}\n`);
  return { ok: true, path: resolve(output) };
}

function doctor() {
  const commands = Object.fromEntries(["ffmpeg", "ffprobe", "python3", "python"].map((name) => [name, commandVersion(name)]));
  const playwright = existsSync(dataPath("node_modules/playwright"));
  return { version: 1, platform: { system: platform(), node: process.version }, ready: commands.ffmpeg.available && commands.ffprobe.available, capabilities: { commands, htmlMotion: { available: playwright, setup: "npm install playwright && npx playwright install chromium" } } };
}

function validate(values) {
  const path = requirePositional(values, "CompositionSpec path");
  const spec = JSON.parse(readFileSync(path, "utf8"));
  validateComposition(spec);
  return { ok: true, path: resolve(path), schemaVersion: spec.schemaVersion };
}

function inspect(values) {
  const path = requirePositional(values, "path");
  if (!path.endsWith(".json")) return python("inspect", values);
  const spec = JSON.parse(readFileSync(path, "utf8"));
  validateComposition(spec);
  return { kind: "composition", valid: true, id: spec.id, durationFrames: spec.durationFrames };
}

function catalogCommand(values) {
  const [subcommand, query] = positional(values);
  if (subcommand === "list") return catalog().items;
  if (subcommand === "search") return searchCatalog(query ?? "");
  if (subcommand === "open") {
    const path = dataPath("site/index.html");
    if (!values.includes("--no-browser")) open(path);
    return { ok: true, path };
  }
  throw new Error("catalog requires list, search, or open");
}

function examplesCommand(values) {
  const [subcommand, id, destination = "."] = positional(values);
  const root = dataPath("examples");
  if (subcommand === "list") return readdirSync(root, { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
  if (subcommand === "create") {
    if (!id) throw new Error("examples create requires an example ID");
    return { ok: true, path: createExample(id, destination) };
  }
  throw new Error("examples requires list or create");
}

function skillsCommand(values) {
  const [subcommand, id] = positional(values);
  if (subcommand === "list") return listSkills();
  if (!id) throw new Error(`skills ${subcommand} requires a skill ID`);
  const options = { harness: option(values, "--harness"), scope: option(values, "--scope") ?? "project", cwd: process.cwd() };
  if (!options.harness) throw new Error(`skills ${subcommand} requires --harness`);
  if (subcommand === "install") return installSkill(id, options);
  if (subcommand === "check") return checkSkill(id, options);
  if (subcommand === "update") return updateSkill(id, options);
  if (subcommand === "remove") return removeSkill(id, options);
  throw new Error("skills requires list, install, check, update, or remove");
}

function python(name, values) {
  for (const executable of ["python3", "python", "py"]) {
    const prefix = executable === "py" ? ["-3"] : [];
    const result = spawnSync(executable, [...prefix, "-m", "vibeedit", name, ...values], { encoding: "utf8" });
    if (result.error?.code === "ENOENT") continue;
    if (result.status !== 0) throw new Error((result.stderr || result.stdout || `Python VibeEdit exited ${result.status}`).trim());
    const output = result.stdout.trim();
    if (jsonOutput(values)) return JSON.parse(output);
    return output;
  }
  throw new Error('media commands require the Python distribution: pip install "vibeedit[all]"');
}

function commandVersion(name) {
  const result = spawnSync(name, ["-version"], { encoding: "utf8" });
  if (result.error?.code === "ENOENT") return { available: false, version: null };
  return { available: result.status === 0, version: (result.stdout || result.stderr).split("\n")[0] };
}

function open(path) {
  const commands = { darwin: ["open", [path]], win32: ["cmd", ["/c", "start", "", path]], linux: ["xdg-open", [path]] };
  const [executable, args] = commands[process.platform] ?? commands.linux;
  spawnSync(executable, args, { stdio: "ignore" });
}

function option(values, name) { const index = values.indexOf(name); return index === -1 ? undefined : values[index + 1]; }
function positional(values) { const optionsWithValues = new Set(["--width", "--height", "--fps", "--frames", "--id", "--output", "--spec", "--harness", "--scope"]); return values.filter((value, index) => !value.startsWith("--") && !optionsWithValues.has(values[index - 1])); }
function requirePositional(values, label) { const value = positional(values)[0]; if (!value) throw new Error(`missing ${label}`); return value; }
function jsonOutput(values) { return values.includes("--json"); }
function format(value) { return typeof value === "string" ? value : JSON.stringify(value, null, 2); }
