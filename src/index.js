import { VERSION } from "./version.js";

export const vibeedit = Object.freeze({
  name: "VibeEdit",
  version: VERSION,
  website: "https://vibeedit.com",
  npm: "https://www.npmjs.com/package/vibeedit",
  schemaVersion: "1.0.0",
  catalogVersion: "0.1.0",
});

export { VERSION } from "./version.js";
export * from "./spec.js";
export * from "./validation.js";
export * from "./motion/index.js";
export * from "./catalog.js";
export * from "./examples.js";
export * from "./skills.js";
export default vibeedit;
