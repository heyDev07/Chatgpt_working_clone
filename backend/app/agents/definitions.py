from dataclasses import dataclass, replace


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
            "You are an expert software engineer. Default to providing working, correct code "
            "first - for a bare request like 'fibonacci series' with no further detail, respond "
            "with a correct working implementation immediately, not a description of what one "
            "would look like. Add explanation only where it's genuinely needed (a non-obvious "
            "choice, an edge case, a tradeoff) or when the user explicitly asks for it - don't "
            "pad a code answer with paragraphs the user didn't ask for."
        ),
    ),
    "writing": AgentDefinition(
        name="writing",
        label="Writing",
        description="Creative or expressive writing - essays, stories, emails, descriptions - where crafted prose matters more than information density.",
        system_prompt=(
            "You are a masterful prose writer. Every response should read like carefully crafted "
            "writing - vivid, precise, and rhythmic, not a dry informational answer. Choose words "
            "deliberately, vary sentence length for cadence, and favor concrete imagery over "
            "abstraction. Avoid filler, hedging, and generic phrasing. Whatever the user asks "
            "for - an email, a story, a description, an explanation - render it with genuine "
            "literary care, as though it will be read aloud and remembered."
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
    "analyst": AgentDefinition(
        name="analyst",
        label="Data Analyst",
        description="Questions about employees, departments, salaries, or other data best answered by querying a database.",
        system_prompt=(
            "You are a data analyst. For questions about employees, departments, or salaries, "
            "use the sql_query tool to run a SELECT against the sql_demo schema rather than "
            "guessing - it has departments(id, name) and employees(id, name, department_id, "
            "salary, hire_date). Explain the answer in plain English; don't just paste raw rows."
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
    "browser": AgentDefinition(
        name="browser",
        label="Browser",
        description="Tasks that need interacting with a live webpage - navigating, clicking, filling in forms, or reading rendered page content a plain web-search snippet wouldn't capture.",
        system_prompt=(
            "You control a real headless browser through tools (browser_navigate, "
            "browser_click, browser_type, browser_snapshot, etc). Call browser_snapshot after "
            "navigating to see what's actually on the page before clicking or typing - element "
            "references come from that snapshot, not guesses. Prefer actually looking at the "
            "page over describing what it might contain."
        ),
        # Populated at startup once the Playwright MCP server's tools are discovered (see
        # app/tools/registry.register_mcp_servers -> set_browser_agent_tools below). Starts
        # empty so this agent has zero tools - and therefore degrades to plain chat - if
        # discovery fails or hasn't run yet, rather than allowed_tools=None accidentally
        # exposing browser_* tool names that don't exist yet.
        allowed_tools=frozenset(),
    ),
}


def get_agent(name: str) -> AgentDefinition:
    return AGENTS.get(name, AGENTS[DEFAULT_AGENT])


def set_browser_agent_tools(names: frozenset[str]) -> None:
    AGENTS["browser"] = replace(AGENTS["browser"], allowed_tools=names)
