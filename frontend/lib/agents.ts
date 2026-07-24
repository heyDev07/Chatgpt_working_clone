// Mirrors app/agents/definitions.py's AGENTS registry labels - a small, fixed set, so a
// constant map here avoids needing a dedicated API endpoint just to fetch a handful of label
// strings.
export const AGENT_LABELS: Record<string, string> = {
  general: "General",
  coding: "Coding",
  research: "Research",
  analyst: "Data Analyst",
  browser: "Browser",
  reviewer: "Reviewer",
};

export function agentLabel(name: string | null | undefined): string | null {
  if (!name) return null;
  return AGENT_LABELS[name] ?? name;
}
