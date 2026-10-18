import Ajv2020 from "ajv/dist/2020";
import type { ErrorObject, ValidateFunction } from "ajv";
import { PrimitiveLegacyError, PrimitiveValidationError } from "./errors";
import schemaDocument from "./generated/schema.json";
import {
  primitiveValidationErrors,
  runPrimitiveTreeValidator,
  runPrimitiveValidator,
} from "./generated/validators.gen";
import type { Primitive, PrimitiveAction } from "./generated/types.gen";

/** Stands in for a node type this client does not know; the renderer draws it as a table. */
export interface FallbackNode {
  type: "__fallback";
  original: string;
  /** The node's first scalar fields, at most `FALLBACK_FIELD_LIMIT`. */
  fields: [string, string][];
  children: RenderNode[];
}

/** A pre-191a button whose action was a free-form string; it can no longer run. */
export interface LegacyButtonNode {
  type: "__legacy_button";
  label: string;
  style?: "primary" | "secondary" | "danger";
}

export type RenderNode = Primitive | FallbackNode | LegacyButtonNode;
export type PrimitiveTree = RenderNode[];
export type PrimitiveNode = RenderNode;
export type { PrimitiveAction };

export const FALLBACK_FIELD_LIMIT = 12;

export interface ParseOptions {
  /** The tree's `ui_version`. Absent or a 1.x version parses in legacy mode. */
  version?: string | null;
}

const ajv = new Ajv2020({ allErrors: true, strict: false, allowUnionTypes: true });
const mapping = schemaDocument.discriminator.mapping as Record<string, string>;
const nodeValidators = new Map<string, ValidateFunction>();

function nodeValidator(type: string): ValidateFunction {
  let validator = nodeValidators.get(type);
  if (!validator) {
    validator = ajv.compile({
      $schema: schemaDocument.$schema,
      $defs: schemaDocument.$defs,
      $ref: mapping[type],
    });
    nodeValidators.set(type, validator);
  }
  return validator;
}

export function validatePrimitive(data: unknown): data is Primitive {
  return runPrimitiveValidator(data);
}

export function validatePrimitiveTree(data: unknown): data is Primitive[] {
  return runPrimitiveTreeValidator(data);
}

export function parsePrimitive(data: unknown): Primitive {
  if (!runPrimitiveValidator(data)) {
    throw PrimitiveValidationError.fromAjvErrors(primitiveValidationErrors(data));
  }
  return data as Primitive;
}


function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isLegacyVersion(version: string | null | undefined): boolean {
  return version == null || /^1(\.|$)/.test(version);
}

function pointer(parts: readonly (string | number)[]): string {
  return parts.map((p) => `/${String(p).replace(/~/g, "~0").replace(/\//g, "~1")}`).join("");
}

/** The errors of the branch the node's `kind` selects, or the first error when none does. */
function relevantErrors(errors: ErrorObject[]): ErrorObject[] {
  const wrongBranch = new Set<string>();
  for (const e of errors) {
    if (e.keyword === "const" && e.instancePath.endsWith("/kind")) {
      wrongBranch.add(e.schemaPath.slice(0, e.schemaPath.indexOf("/properties/")));
    }
  }
  const kept = errors.filter(
    (e) =>
      e.keyword !== "oneOf" &&
      ![...wrongBranch].some((branch) => e.schemaPath.startsWith(`${branch}/`)),
  );
  return kept.length > 0 ? kept : errors;
}

function nodeError(nodePath: (string | number)[], errors: ErrorObject[]): PrimitiveValidationError {
  const issues = relevantErrors(errors).map((e) => {
    const missing = e.params?.missingProperty as string | undefined;
    const field = e.instancePath + (missing ? `/${missing}` : "");
    return {
      path: pointer(nodePath) + field,
      message: e.message ?? "Validation failed",
      keyword: e.keyword,
    };
  });
  const first = issues[0] ?? { path: pointer(nodePath), message: "Invalid primitive" };
  return new PrimitiveValidationError(`${first.path}: ${first.message}`, first.path, issues);
}

function nestedNodes(value: unknown): value is Record<string, unknown>[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((v) => isRecord(v) && typeof v.type === "string")
  );
}

function fallbackNode(
  raw: Record<string, unknown>,
  path: (string | number)[],
  legacy: boolean,
): FallbackNode {
  const fields: [string, string][] = [];
  const children: RenderNode[] = [];
  for (const [key, value] of Object.entries(raw)) {
    if (key === "type") continue;
    if (nestedNodes(value)) {
      value.forEach((child, i) => children.push(parseNode(child, [...path, key, i], legacy)));
    } else if (
      fields.length < FALLBACK_FIELD_LIMIT &&
      (typeof value === "string" || typeof value === "number" || typeof value === "boolean")
    ) {
      fields.push([key, String(value)]);
    }
  }
  return { type: "__fallback", original: String(raw.type), fields, children };
}

function parseNode(raw: unknown, path: (string | number)[], legacy: boolean): RenderNode {
  if (!isRecord(raw) || typeof raw.type !== "string") {
    const message = `${pointer(path)}: must be an object with a string type`;
    const issue = { path: pointer(path), message: "must be an object with a string type" };
    throw new PrimitiveValidationError(message, issue.path, [issue]);
  }
  if (!(raw.type in mapping)) return fallbackNode(raw, path, legacy);

  if (legacy && raw.type === "button" && typeof raw.action === "string") {
    return {
      type: "__legacy_button",
      label: String(raw.label ?? ""),
      ...(typeof raw.style === "string" ? { style: raw.style as LegacyButtonNode["style"] } : {}),
    };
  }

  const children = Array.isArray(raw.children) ? raw.children : null;
  const validator = nodeValidator(raw.type);
  if (!validator(children ? { ...raw, children: [] } : raw)) {
    throw nodeError(path, validator.errors ?? []);
  }
  if (!children) return raw as unknown as Primitive;
  return {
    ...raw,
    children: children.map((child, i) => parseNode(child, [...path, "children", i], legacy)),
  } as unknown as Primitive;
}

/**
 * Parses a tree node by node. A known node is strict and a failure names the node's path and field;
 * an unknown type becomes a fallback node, so a newer backend never blanks the whole view. A tree
 * with no version or a 1.x version is legacy: its string-action buttons parse as disabled buttons.
 */
export function parsePrimitiveTree(data: unknown, options: ParseOptions = {}): PrimitiveTree {
  const legacy = isLegacyVersion(options.version);
  try {
    if (!Array.isArray(data) || data.length === 0) {
      const issue = { path: "/", message: "must be a non-empty array" };
      throw new PrimitiveValidationError(`${issue.path}: ${issue.message}`, issue.path, [issue]);
    }
    return data.map((node, i) => parseNode(node, [i], legacy));
  } catch (error) {
    if (legacy && error instanceof PrimitiveValidationError) throw new PrimitiveLegacyError(error);
    throw error;
  }
}
