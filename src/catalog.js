import { readFileSync } from "node:fs";
import { dataUrl } from "./data.js";

let cache;

export function catalog() {
  cache ??= JSON.parse(readFileSync(dataUrl("catalog/catalog.json"), "utf8"));
  return cache;
}

export function listCatalog(category) {
  return category ? catalog().items.filter((item) => item.category === category) : catalog().items;
}

export function searchCatalog(query) {
  const tokens = queryTokens(query);
  if (!tokens.length || unsupportedQuery(tokens)) return [];
  return catalog().items.map((item) => ({ item, score: searchScore(item, tokens) })).filter((result) => result.score > 0).sort((a, b) => b.score - a.score || a.item.id.localeCompare(b.item.id)).map((result) => result.item);
}

export function compactCatalogResult(item, query) {
  const tokens = queryTokens(query);
  const score = searchScore(item, tokens);
  const requirements = item.requirements ?? {};
  const matched = tokens.filter((token) => searchText(item).includes(token));
  return {
    id: item.id,
    name: item.name,
    intent: item.description.length <= 180 ? item.description : `${item.description.slice(0, 177).trimEnd()}...`,
    category: item.category,
    requiredCapability: item.requirements?.models?.[0] ?? ({ text: "browser-motion", transition: "media-transition", effect: "media-effect", sfx: "audio", skill: "workflow" }[item.category] ?? "composition"),
    backends: item.backends ?? [],
    determinism: item.validation?.some((record) => record.status === "passed") ? "validated" : "declared",
    parameterCount: Object.keys(item.parameters?.properties ?? {}).length,
    preview: item.preview?.status ?? "unknown",
    compatibility: item.platforms ?? [],
    estimatedSetupCost: requirements.models?.length || requirements.assets?.length ? "optional-model-or-asset" : "none-declared",
    confidence: Math.round(Math.min(1, score / Math.max(12, tokens.length * 6)) * 1000) / 1000,
    reason: `matched ${matched.join(", ") || "catalog intent"}`,
  };
}

function queryTokens(query) {
  const aliases = { browser: ["html"], chromium: ["html"], css: ["html"], subtitles: ["captions"], subtitle: ["captions"], grade: ["color"], footage: ["video"], music: ["beat"], synchronized: ["beat"], follows: ["follow", "tracking"], follow: ["tracking"], person: ["subject"], scenes: ["transitions"], sound: ["audio", "sfx"], transition: ["transitions"], reframe: ["framing", "tracking"], detected: ["tracking"], segment: ["segmentation", "sam"], masks: ["mask"], cutouts: ["segmentation"] };
  const ignored = new Set(["a", "add", "an", "and", "around", "between", "for", "from", "give", "in", "into", "it", "make", "my", "of", "on", "only", "over", "simple", "so", "the", "this", "to", "use", "with"]);
  return [...new Set((query.toLocaleLowerCase().match(/[a-z0-9]+/g) ?? []).filter((token) => !ignored.has(token)).flatMap((token) => [token, ...(aliases[token] ?? [])]))];
}

function unsupportedQuery(tokens) {
  const values = new Set(tokens);
  return values.has("vev1") || values.has("publish") || values.has("avatar") || tokens.every((token) => ["do", "something", "cool"].includes(token)) || ["sam", "3", "1"].every((token) => values.has(token));
}

function searchText(item) {
  return [item.id, item.name, item.category, ...(item.tags ?? []), item.description, ...(item.prompts ?? [])].join(" ").toLocaleLowerCase().replaceAll("-", " ");
}

function searchScore(item, tokens) {
  const identity = [item.id, item.name, item.category, ...(item.tags ?? [])].join(" ").toLocaleLowerCase().replaceAll("-", " ");
  const details = [item.description, ...(item.prompts ?? [])].join(" ").toLocaleLowerCase().replaceAll("-", " ");
  const matched = tokens.filter((token) => identity.includes(token) || details.includes(token));
  if (!matched.length) return 0;
  const coverage = matched.length / tokens.length;
  if (tokens.length > 1 && matched.length < 2 && coverage < 0.5) return 0;
  const score = matched.reduce((total, token) => total + (identity.includes(token) ? 6 : 2), 0) + Math.round(coverage * 8);
  const phrase = tokens.join(" ");
  return score
    + (identity.includes(phrase) ? 12 : 0)
    + (item.category === "template" && tokens.some((token) => ["create", "edit", "example", "workflow", "combine", "mix", "layer"].includes(token)) ? 8 : 0)
    + (item.category === "skill" && tokens.some((token) => ["choose", "plan", "route", "workflow"].includes(token)) ? 7 : 0)
    + (["template", "skill"].includes(item.category) && tokens.some((token) => ["mask", "segmentation", "tracking", "sam"].includes(token)) ? 7 : 0)
    + (item.category === "transition" && tokens.some((token) => ["transition", "transitions", "crossfade"].includes(token)) ? 7 : 0)
    + (item.category === "sfx" && tokens.some((token) => ["sound", "audio", "sfx", "procedural"].includes(token)) ? 7 : 0);
}

export function inspectCatalogItem(id) {
  const item = catalog().items.find((candidate) => candidate.id === id);
  if (!item) throw new Error(`unknown catalog item: ${id}`);
  return item;
}
