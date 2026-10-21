import { parsePrimitiveTree, PrimitiveLegacyError, type PrimitiveTree } from "@myguyze/ze-ui";

export type ParsedTree =
  | { status: "ok"; nodes: PrimitiveTree }
  /** A tree stored before the typed-action contract that cannot be shown even in legacy mode. */
  | { status: "legacy-failed" }
  | { status: "invalid" };

/** Parses a tree under the version its transport carried. An absent version stays absent: it means legacy. */
export function parseTree(components: unknown, version: string | null | undefined): ParsedTree {
  try {
    return { status: "ok", nodes: parsePrimitiveTree(components, { version }) };
  } catch (error) {
    return { status: error instanceof PrimitiveLegacyError ? "legacy-failed" : "invalid" };
  }
}
