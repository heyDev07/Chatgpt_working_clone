from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    label: str
    # Shown to the coordinator's classifier so it knows when to pick this agent - keep these
    # mutually distinguishable, not just a restatement of the agent's name.
    description: str
    system_prompt: str
    allowed_tools: frozenset[str] | None = None  # None = every registered tool is allowed


DEFAULT_AGENT = "general"

AGENTS: dict[str, AgentDefinition] = {
    "general": AgentDefinition(
        name="general",
        label="General",
        description="Default assistant for everyday questions, conversation, or anything that doesn't need a specialist.",
        system_prompt="",  # no override - the conversation's own system_prompt (if any) applies unmodified
    ),
    "coding": AgentDefinition(
        name="coding",
        label="Coding",
        description="Writing, explaining, reviewing, or debugging code; software architecture and implementation questions.",
        system_prompt=(
            "You are an expert software engineer. Prioritize correct, idiomatic code and precise "
            "technical explanations. Call out edge cases, tradeoffs, and potential bugs. Prefer "
            "concrete code over vague advice."
        ),
    ),
    "research": AgentDefinition(
        name="research",
        label="Research",
        description="Fact-finding, analysis, or questions that benefit from step-by-step reasoning and calculation.",
        system_prompt=(
            "You are a meticulous research assistant. Break the question down, reason step by "
            "step, and use available tools (e.g. the calculator) rather than guessing at numeric "
            "answers. Be explicit about uncertainty instead of stating unverified claims as fact."
        ),
    ),
    "reviewer": AgentDefinition(
        name="reviewer",
        label="Reviewer",
        description="Critiquing or reviewing something the user already wrote, or finding flaws/improvements in prior output.",
        system_prompt=(
            "You are a rigorous, constructive critic. Identify concrete flaws, gaps, and risks "
            "before offering praise. Every criticism should come with a specific, actionable fix."
        ),
    ),
}


def get_agent(name: str) -> AgentDefinition:
    return AGENTS.get(name, AGENTS[DEFAULT_AGENT])
