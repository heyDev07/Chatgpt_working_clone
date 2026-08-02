"use client";

import { Check, Loader2 } from "lucide-react";

import { agentLabel } from "@/lib/agents";
import type { PlanEventData } from "@/lib/api/stream";

// Shown once decomposition completes (see orchestrator_service.py's/research_service.py's "plan"
// event) so the user sees the whole multi-step breakdown upfront, not just whichever subtask
// happens to be running. activeStepIndex counts "agent" events received since this plan started
// (see ChatWindow.tsx's agentEventCount) rather than matching by agent *name* - the orchestrator's
// steps have distinct specialist names, but research_service.py's steps all share the same
// "deep_research" persona for different sub-questions, so name-matching would always resolve to
// the first step. Position-in-arrival-order is correct for both, since each service emits exactly
// one "agent" event per step, in order.
export function OrchestratorPlan({ plan, activeStepIndex }: { plan: PlanEventData; activeStepIndex: number }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-black/10 dark:border-white/10 px-3 py-2 text-xs">
      {plan.steps.map((step, i) => {
        const isDone = activeStepIndex >= 0 && i < activeStepIndex;
        const isActive = i === activeStepIndex;
        return (
          <div key={i} className="flex items-center gap-2">
            {isDone ? (
              <Check size={12} className="flex-shrink-0 text-green-600 dark:text-green-500" />
            ) : isActive ? (
              <Loader2 size={12} className="flex-shrink-0 animate-spin text-black/50 dark:text-white/50" />
            ) : (
              <div className="h-3 w-3 flex-shrink-0 rounded-full border border-black/20 dark:border-white/20" />
            )}
            <span className={isActive ? "text-black/80 dark:text-white/80" : "text-black/50 dark:text-white/50"}>
              <span className="font-medium">{agentLabel(step.agent)}:</span> {step.task}
            </span>
          </div>
        );
      })}
    </div>
  );
}
