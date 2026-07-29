// Mirrors app/agents/definitions.py's AGENTS registry labels - a small, fixed set, so a
// constant map here avoids needing a dedicated API endpoint just to fetch a handful of label
// strings.
export const AGENT_LABELS: Record<string, string> = {
  general: "General",
  coding: "Coding",
  writing: "Writing",
  research: "Research",
  analyst: "Data Analyst",
  browser: "Browser",
  reviewer: "Reviewer",
  // Not a real LLM persona - stream_search's agent event reuses this same field/pill so the
  // message list can render it consistently, even though no agent classification (or LLM call
  // at all) actually happened for it.
  web_search: "Web Search",
  // orchestrator_service.py persists the *synthesized* final message under this agent name -
  // the individual subtask agents (research/coding/etc) only ever appear transiently via the
  // live "agent" stream events while that turn is still in progress, not on the saved message.
  orchestrator: "Agent",
};

export function agentLabel(name: string | null | undefined): string | null {
  if (!name) return null;
  return AGENT_LABELS[name] ?? name;
}
