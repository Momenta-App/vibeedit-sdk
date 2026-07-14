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
  const needle = query.toLocaleLowerCase();
  return catalog().items.filter((item) => JSON.stringify(item).toLocaleLowerCase().includes(needle));
}

export function inspectCatalogItem(id) {
  const item = catalog().items.find((candidate) => candidate.id === id);
  if (!item) throw new Error(`unknown catalog item: ${id}`);
  return item;
}
