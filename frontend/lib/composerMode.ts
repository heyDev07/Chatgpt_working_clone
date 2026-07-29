// "auto" is the existing, untouched behavior - classify_agent() picks a persona per message,
// exactly as it always has. "coding"/"writing" skip the classifier and force that persona's
// system prompt (same AGENTS registry, just not auto-selected); "search" doesn't call the LLM at
// all, routing to a completely different backend endpoint (see lib/api/stream.ts's
// searchMessage). "agent" also routes to its own endpoint (orchestrateMessage) - it decomposes
// the request into subtasks across multiple specialist personas and synthesizes one final
// answer, for compound requests a single persona can't cleanly cover (see
// orchestrator_service.py's docstring).
export type ComposerMode = "auto" | "coding" | "writing" | "search" | "agent";

export const COMPOSER_MODES: { value: ComposerMode; label: string; description: string }[] = [
  { value: "auto", label: "Auto", description: "The assistant picks the right approach for you" },
  { value: "coding", label: "Code", description: "Straight to working code, minimal explanation" },
  { value: "writing", label: "Write", description: "Crafted, literary prose" },
  { value: "search", label: "Search", description: "Direct web search, no AI model involved" },
  { value: "agent", label: "Agent", description: "Breaks compound requests into specialist subtasks" },
];
