const LABELS: Record<string, string> = {
  "automation.accountability": "Accountability notes",
  "calendar.calendar_reminders": "Calendar reminders",
  "calendar.reminders": "Reminders",
  "confirmations": "Pending approvals",
  "contacts.channels": "Contact channels",
  "contacts.persons": "People",
  "contacts.sources": "Contact sources",
  "feedback.records": "Reply feedback",
  "finance.accounts": "Finance accounts",
  "finance.csv_mappings": "Finance import mappings",
  "finance.positions": "Finance positions",
  "finance.recurring": "Recurring payments",
  "finance.transactions": "Finance transactions",
  "goals.gates": "Goal gates",
  "goals.goals": "Goals",
  "goals.learning_evidence": "Goal learning evidence",
  "goals.learnings": "Goal learnings",
  "goals.milestones": "Goal milestones",
  "goals.suggestions": "Goal suggestions",
  "goals.traces": "Goal run history",
  "graph.checkpoints": "Conversation state",
  "memory.entities": "Entities",
  "memory.episodes": "Episodes",
  "memory.events": "Events",
  "memory.facts": "Facts",
  "memory.insights": "Insights",
  "memory.procedures": "Procedures",
  "memory.profile_facets": "Profile",
  "memory.relationships": "Relationships",
  "memory.task_state": "Task state",
  "messages.store": "Messages",
  "onboarding": "Onboarding",
  "persona.state": "Persona",
  "proactive.interruption_settings": "Quiet hours",
  "proactive.log": "Push history",
  "prospecting.campaigns": "Prospecting campaigns",
  "prospecting.outreach": "Prospecting outreach",
  "routing.log": "Routing history",
  "sessions": "Sessions",
  "telemetry.costs": "Spend history",
  "workflow.executions": "Workflow runs",
  "workflow.workflows": "Workflows",
  "worldstate.open_loops": "Open loops",
};

/** Plain words for a data domain id; an unknown id is humanised, never shown as a table name. */
export function domainLabel(id: string): string {
  const known = LABELS[id];
  if (known) return known;
  const last = id.split(".").pop() ?? id;
  const words = last.replace(/_/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
