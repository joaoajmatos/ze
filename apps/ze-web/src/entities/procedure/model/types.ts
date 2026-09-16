export type ProcedureEvidenceRef = {
  kind: string;
  id: string;
};

export type ProcedureCandidate = {
  id: string;
  source_kind: string;
  provenance: string;
  name: string;
  trigger: string;
  preconditions: string[];
  steps: string[];
  success_criteria: string[];
  limits: string[];
  evidence_refs: ProcedureEvidenceRef[];
  learning_refs: string[];
  status: string;
  submitted_at: string | null;
  resolved_at: string | null;
};

export type ProcedureSummary = {
  id: string;
  name: string;
  identity_status: string;
  version_status: string;
  version_number: number;
  trigger: string;
  current_version_id: string | null;
  evidence_refs: ProcedureEvidenceRef[];
};

export type ProcedureVersion = {
  id: string;
  procedure_id: string;
  version_number: number;
  name: string;
  trigger: string;
  preconditions: string[];
  steps: string[];
  success_criteria: string[];
  limits: string[];
  provenance: string;
  status: string;
  evidence_refs: ProcedureEvidenceRef[];
  learning_refs: string[];
};

export type ProcedureDetail = {
  id: string;
  name: string;
  identity_status: string;
  current_version_id: string | null;
  versions: ProcedureVersion[];
  events: { kind: string; reason: string; version_id: string | null }[];
  outcomes: { outcome: string; summary: string; procedure_version_id: string }[];
};

export type ProcedureAdmissionResult = {
  candidate: ProcedureCandidate;
  version: { id: string; status: string } | null;
};
