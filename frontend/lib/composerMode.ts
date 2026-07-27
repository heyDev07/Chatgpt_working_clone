// "auto" is the existing, untouched behavior - classify_agent() picks a persona per message,
// exactly as it always has. The other three are explicit user overrides: "coding"/"writing" skip
// the classifier and force that persona's system prompt (same AGENTS registry, just not
// auto-selected); "search" doesn't call the LLM at all, routing to a completely different
// backend endpoint (see lib/api/stream.ts's searchMessage).
export type ComposerMode = "auto" | "coding" | "writing" | "search";

export const COMPOSER_MODES: { value: ComposerMode; label: string; description: string }[] = [
  { value: "auto", label: "Auto", description: "The assistant picks the right approach for you" },
  { value: "coding", label: "Code", description: "Straight to working code, minimal explanation" },
  { value: "writing", label: "Write", description: "Crafted, literary prose" },
  { value: "search", label: "Search", description: "Direct web search, no AI model involved" },
];
