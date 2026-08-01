"""Custom application metrics, alongside the standard HTTP metrics
prometheus-fastapi-instrumentator already provides automatically (request count/latency/in-progress
by method+path+status - see main.py's setup_metrics()). These cover what that library can't infer
on its own: LLM call cost/latency by provider+model, and tool call outcomes by tool name -
the same duration/success data tool_call_logs already records for audit purposes, but as
real-time counters/histograms a Grafana dashboard can actually graph, not a table to query."""

from prometheus_client import Counter, Histogram

llm_requests_total = Counter(
    "llm_requests_total",
    "Completed chat turns, by provider/model/outcome",
    ["provider", "model", "finish_reason"],
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "Wall-clock time for a full chat turn (all tool-calling iterations included)",
    ["provider", "model"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
)

llm_tokens_total = Counter(
    "llm_tokens_total",
    "Completion tokens generated, by provider/model",
    ["provider", "model"],
)

tool_calls_total = Counter(
    "tool_calls_total",
    "Tool invocations, by tool name and outcome",
    ["tool_name", "success"],
)

tool_call_duration_seconds = Histogram(
    "tool_call_duration_seconds",
    "Tool execution time, by tool name",
    ["tool_name"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

semantic_cache_lookups_total = Counter(
    "semantic_cache_lookups_total",
    "Semantic cache lookups attempted for eligible turns, by result",
    ["result"],  # "hit" or "miss"
)
