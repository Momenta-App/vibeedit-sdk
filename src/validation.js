import { readFileSync } from "node:fs";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { dataUrl } from "./data.js";

const schema = JSON.parse(readFileSync(dataUrl("schema/composition.schema.json"), "utf8"));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile(schema);

export class CompositionValidationError extends TypeError {
  constructor(errors) {
    super(`invalid CompositionSpec\n${errors.map((error) => `${path(error.instancePath)}: ${error.message}`).join("\n")}`);
    this.name = "CompositionValidationError";
    this.errors = errors;
  }
}

export function validateComposition(spec) {
  if (validate(spec)) return spec;
  throw new CompositionValidationError(validate.errors ?? []);
}

export function canonicalJson(value) {
  return JSON.stringify(sort(value));
}

function sort(value) {
  if (Array.isArray(value)) return value.map(sort);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => [key, sort(item)]));
}

function path(pointer) {
  return pointer ? `$${pointer.replaceAll("/", ".")}` : "$";
}
