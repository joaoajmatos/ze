export type {
  UiContributionSchema as UiContribution,
  UiManifestResponse as UiManifest,
  UiModuleResponse,
} from "@myguyze/ze-client";

export type ModuleSlot = "mind.entity" | "doing.run" | "governance.connections";

/** What a slot passes to its modules; Ze reads the labels and types from its own records. */
export interface ModuleSubject {
  kind: "entity" | "workflow_run" | "none";
  id?: string;
  /** Display-only; never sent. The server reads the label and type from its own records. */
  label?: string;
  entity_type?: string;
  /** The workflow id, for a run. */
  parent_id?: string;
}
