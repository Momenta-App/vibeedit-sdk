import { fileURLToPath } from "node:url";

export function dataUrl(path) {
  return new URL(`../${path}`, import.meta.url);
}

export function dataPath(path) {
  return fileURLToPath(dataUrl(path));
}
