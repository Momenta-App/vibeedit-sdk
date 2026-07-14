import { cpSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { dataPath } from "./data.js";

export function createExample(id, destination = ".") {
  const source = dataPath(`examples/${id}`);
  const target = resolve(destination, id);
  if (!existsSync(source)) throw new Error(`unknown example: ${id}`);
  if (existsSync(target)) throw new Error(`destination already exists: ${target}`);
  cpSync(source, target, { recursive: true });
  return target;
}
