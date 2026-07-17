#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { platform } from "node:os";
import { join, resolve } from "node:path";
import process from "node:process";
import { catalog, checkSkill, compactCatalogResult, createExample, installSkill, listSkills, removeSkill, searchCatalog, updateSkill, validateComposition } from "../src/index.js";
import { dataPath } from "../src/data.js";
import { VERSION } from "../src/version.js";

const [command, ...args] = process.argv.slice(2);

if (!command || ["help", "--help", "-h"].includes(command)) {
  console.log(help());
  process.exit(0);
}

if (["version", "--version", "-V"].includes(command)) {
  console.log(`vibeedit ${VERSION}`);
  process.exit(0);
}

if (args.some((value) => ["help", "--help", "-h"].includes(value))) {
  console.log(commandHelp(command));
  process.exit(0);
}

try {
  const result = await route(command, args);
  if (result !== undefined) console.log(jsonOutput(args) ? JSON.stringify(result, null, 2) : format(result));
} catch (error) {
  if (jsonOutput(args)) console.log(JSON.stringify({ ok: false, error: error.message }));
  else console.error(`vibeedit: ${error.message.replace(/^vibeedit:\s*/, "")}`);
  process.exitCode = 1;
}

async function route(name, values) {
  if (name === "init") return init(values);
  if (name === "doctor") return doctor(values);
  if (name === "validate") return validate(values);
  if (name === "inspect") return inspect(values);
  if (name === "catalog") return catalogCommand(values);
  if (name === "examples") return examplesCommand(values);
  if (name === "skills") return skillsCommand(values);
  if (["setup", "preview", "render", "verify", "clean", "mcp"].includes(name)) return python(name, values);
  throw new Error(`unknown command: ${name}. Run \`vibeedit --help\` to see supported commands.`);
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
    provenance: { generator: "vibeedit-node", generatorVersion: VERSION, createdAt: new Date().toISOString(), schemaSource: "schema/composition.schema.json" },
  };
  validateComposition(spec);
  writeFileSync(output, `${JSON.stringify(spec, null, 2)}\n`);
  return { ok: true, path: resolve(output) };
}

async function doctor(values) {
  const commands = Object.fromEntries(["ffmpeg", "ffprobe", "python3", "python"].map((name) => [name, commandVersion(name)]));
  const bridge = pythonBridge();
  const htmlMotion = { available: false, packageInstalled: false, browserInstalled: false, setup: "npm install playwright@1.61.0 && npx playwright install chromium" };
  try {
    const { chromium } = await import("playwright");
    htmlMotion.packageInstalled = true;
    htmlMotion.browserInstalled = existsSync(chromium.executablePath());
    htmlMotion.available = htmlMotion.browserInstalled;
  } catch {}
  const ready = commands.ffmpeg.available && commands.ffprobe.available;
  const result = {
    version: 1,
    platform: { system: platform(), node: process.version },
    ready,
    readiness: {
      level: ready ? "core-ready" : "core-unavailable",
      meaning: ready ? "Core FFmpeg rendering is ready; HTML motion and Python media commands may still require setup." : "Core rendering requires FFmpeg and FFprobe.",
      nextActions: [!htmlMotion.available ? htmlMotion.setup : null, !bridge.available ? 'Install the Python package for media commands: pip install "vibeedit[all]"' : null].filter(Boolean),
    },
    capabilities: { commands, htmlMotion, pythonBridge: bridge },
  };
  if (jsonOutput(values)) return result;
  return [
    `VibeEdit doctor: ${result.readiness.level}`,
    result.readiness.meaning,
    `HTML motion: ${htmlMotion.available ? "ready" : "setup required"}`,
    `Python media bridge: ${bridge.available ? `ready (${bridge.executable}, VibeEdit ${bridge.version})` : "not installed"}`,
    ...result.readiness.nextActions.map((action) => `  - ${action}`),
    "Use `vibeedit doctor --json` for command, provider, and version details.",
  ].join("\n");
}

function validate(values) {
  const path = requireFile(requirePositional(values, "CompositionSpec path"), "CompositionSpec");
  const spec = JSON.parse(readFileSync(path, "utf8"));
  validateComposition(spec);
  return { ok: true, path: resolve(path), schemaVersion: spec.schemaVersion };
}

function inspect(values) {
  const path = requireFile(requirePositional(values, "path"), "input");
  if (!path.endsWith(".json")) return python("inspect", values);
  const spec = JSON.parse(readFileSync(path, "utf8"));
  validateComposition(spec);
  return { kind: "composition", valid: true, id: spec.id, durationFrames: spec.durationFrames };
}

function catalogCommand(values) {
  const [subcommand, query] = positional(values);
  if (subcommand === "list") return catalog().items;
  if (subcommand === "search") {
    const limit = Number(option(values, "--limit") ?? 20);
    if (!Number.isInteger(limit) || limit < 1) throw new Error("--limit must be a positive integer; use --all to return every result");
    const items = searchCatalog(query ?? "");
    const selected = values.includes("--all") ? items : items.slice(0, limit);
    if (!values.includes("--compact")) return selected;
    return selected.map((item) => compactCatalogResult(item, query ?? ""));
  }
  if (subcommand === "open") {
    const path = dataPath("site/index.html");
    const opened = values.includes("--browser");
    if (opened) open(path);
    return { ok: true, path, opened };
  }
  throw new Error("catalog requires list, search, or open");
}

function examplesCommand(values) {
  const [subcommand, id, positionalDestination] = positional(values);
  const destination = option(values, "--output") ?? positionalDestination ?? ".";
  const root = dataPath("examples");
  if (subcommand === "list") {
    const items = readdirSync(root, { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
    return values.includes("--details") ? items.map((identifier) => exampleRecord(root, identifier)) : items;
  }
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
  const bridge = pythonBridge();
  if (!bridge.available) throw new Error('media commands require the Python distribution. Install it with: pip install "vibeedit[all]"');
  const result = spawnSync(bridge.executable, [...bridge.prefix, "-m", "vibeedit", name, ...values], { encoding: "utf8" });
  if (result.status !== 0) throw new Error((result.stderr || result.stdout || `Python VibeEdit exited ${result.status}`).trim());
  const output = result.stdout.trim();
  if (jsonOutput(values)) return JSON.parse(output);
  return output;
}

function commandVersion(name) {
  const result = spawnSync(name, name.startsWith("python") ? ["--version"] : ["-version"], { encoding: "utf8" });
  if (result.error?.code === "ENOENT") return { available: false, version: null };
  return { available: result.status === 0, version: (result.stdout || result.stderr).split("\n")[0] };
}

function pythonBridge() {
  for (const executable of ["python3", "python", "py"]) {
    const prefix = executable === "py" ? ["-3"] : [];
    const result = spawnSync(executable, [...prefix, "-c", "import vibeedit; print(vibeedit.__version__)"], { encoding: "utf8" });
    if (result.status === 0) return { available: true, executable, prefix, version: result.stdout.trim() };
  }
  return { available: false, executable: null, prefix: [], version: null };
}

function open(path) {
  const commands = { darwin: ["open", [path]], win32: ["cmd", ["/c", "start", "", path]], linux: ["xdg-open", [path]] };
  const [executable, args] = commands[process.platform] ?? commands.linux;
  spawnSync(executable, args, { stdio: "ignore" });
}

function option(values, name) { const index = values.indexOf(name); return index === -1 ? undefined : values[index + 1]; }
function positional(values) { const optionsWithValues = new Set(["--width", "--height", "--fps", "--frames", "--id", "--output", "--spec", "--harness", "--scope", "--limit"]); return values.filter((value, index) => !value.startsWith("--") && !optionsWithValues.has(values[index - 1])); }
function requirePositional(values, label) { const value = positional(values)[0]; if (!value) throw new Error(`missing ${label}`); return value; }
function requireFile(value, label) { if (existsSync(value)) return value; throw new Error(`${label} not found: ${value}. Run \`vibeedit init composition.json\` or \`vibeedit examples create basic-generated\` first.`); }
function jsonOutput(values) { return values.includes("--json"); }
function format(value) { return typeof value === "string" ? value : JSON.stringify(value, null, 2); }

function exampleRecord(root, identifier) {
  const manifest = join(root, identifier, "manifest.json");
  if (!existsSync(manifest)) return { id: identifier, name: identifier.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()), description: "Packaged executable VibeEdit example.", families: [], requirements: { extras: [], models: [] }, conditional: false, recommended: identifier === "basic-generated" };
  const value = JSON.parse(readFileSync(manifest, "utf8"));
  return { id: identifier, name: value.name, description: value.description, families: value.families, requirements: value.requirements, conditional: value.conditional, recommended: identifier === "basic-generated" };
}

function help() {
  return `VibeEdit ${VERSION}

Frame-accurate video production for JavaScript, HTML/CSS, Python, and AI coding agents.

Usage: vibeedit <command> [options]

Start here:
  vibeedit doctor --json
  vibeedit examples list --details --json
  vibeedit catalog search kinetic --compact --limit 5 --json

Commands:
  init                    Create a validated CompositionSpec
  setup                   Prepare explicitly selected optional runtimes through Python
  doctor                  Report core readiness, optional capabilities, and next actions
  inspect                 Inspect a CompositionSpec or media file
  catalog list|search|open
  examples list|create
  skills list|install|check|update|remove
  validate                Validate a CompositionSpec
  preview|render|verify   Run through the installed Python VibeEdit package
  clean|mcp               Run through the installed Python VibeEdit package

Use vibeedit <command> --help for command-specific guidance.`;
}

function commandHelp(name) {
  const messages = {
    setup: `Usage: vibeedit setup [--browser] [--effects] [--vision] [--sam] [--all] [--json]\n\nSetup runs through the Python package and downloads only explicitly selected runtimes.\n  --browser  Pinned Chromium for HTML/CSS/JS motion\n  --effects  NumPy/Pillow/OpenCV dependencies; no model download\n  --vision   Face/body/pose/object providers; may download a 29.5 MB model\n  --sam      SAM 2.1; downloads about 211.7 MB\n  --all      Every supported optional capability\n\nInstall the Python package first with: pip install "vibeedit[all]"`,
    doctor: "Usage: vibeedit doctor [--json]\n\nReports core FFmpeg readiness separately from optional HTML motion and Python media capabilities.",
    catalog: "Usage: vibeedit catalog search <query> [--compact] [--limit N|--all] [--json]\n       vibeedit catalog open [--browser] [--json]\n\nCatalog open stays in the background unless --browser is explicit.",
    examples: "Usage: vibeedit examples list [--details] [--json]\n       vibeedit examples create <id> [destination|--output directory] [--json]\n\nThe example is created as <directory>/<id> and existing files are never overwritten.",
    render: "Usage: vibeedit render <composition.json> [--output video.mp4] [--json]\n\nRequires the Python package and FFmpeg. Run vibeedit doctor first.",
  };
  return messages[name] ?? help();
}
