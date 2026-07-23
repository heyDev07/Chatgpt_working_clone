"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { getUsageAnalytics, type DailyUsage } from "@/lib/api/admin";

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-black/10 dark:border-white/10 px-4 py-3">
      <div className="text-xs text-black/40 dark:text-white/40">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-black/90 dark:text-white/90">
        {value.toLocaleString()}
      </div>
    </div>
  );
}

// Single-series bar chart. Two different-scale metrics (message count vs. token count) are
// deliberately rendered as two separate charts here rather than one dual-axis chart.
function DailyBarChart({ title, data, valueKey }: { title: string; data: DailyUsage[]; valueKey: "message_count" | "token_count" }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const max = Math.max(1, ...data.map((d) => d[valueKey]));

  return (
    <div className="rounded-lg border border-black/10 dark:border-white/10 p-4">
      <div className="text-xs font-medium text-black/50 dark:text-white/50 mb-3">{title}</div>
      <div className="flex items-end gap-1.5 h-32">
        {data.map((d, i) => {
          const value = d[valueKey];
          const heightPct = (value / max) * 100;
          return (
            <div
              key={d.date}
              className="relative flex-1 flex flex-col items-center justify-end h-full"
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
            >
              {hovered === i && (
                <div className="absolute -top-7 whitespace-nowrap rounded bg-black text-white dark:bg-white dark:text-black text-[10px] px-1.5 py-0.5 z-10">
                  {value.toLocaleString()}
                </div>
              )}
              <div
                className="w-full rounded-t bg-blue-600 dark:bg-blue-500 transition-opacity"
                style={{ height: `${Math.max(heightPct, 2)}%`, opacity: hovered === null || hovered === i ? 1 : 0.4 }}
              />
            </div>
          );
        })}
      </div>
      <div className="flex gap-1.5 mt-1.5">
        {data.map((d) => (
          <div key={d.date} className="flex-1 text-center text-[10px] text-black/30 dark:text-white/30">
            {new Date(d.date).toLocaleDateString(undefined, { month: "numeric", day: "numeric" })}
          </div>
        ))}
      </div>
    </div>
  );
}

export function UsageAnalytics() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-usage-analytics"],
    queryFn: () => getUsageAnalytics(14),
  });

  if (isLoading || !data) {
    return <p className="text-sm text-black/40 dark:text-white/40 mb-6">Loading analytics...</p>;
  }

  return (
    <div className="flex flex-col gap-4 mb-8">
      <div className="grid grid-cols-4 gap-3">
        <StatTile label="Users" value={data.total_users} />
        <StatTile label="Conversations" value={data.total_conversations} />
        <StatTile label="Messages" value={data.total_messages} />
        <StatTile label="Tokens" value={data.total_tokens} />
      </div>

      {data.daily.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          <DailyBarChart title="Messages per day (last 14 days)" data={data.daily} valueKey="message_count" />
          <DailyBarChart title="Tokens per day (last 14 days)" data={data.daily} valueKey="token_count" />
        </div>
      )}

      {data.top_users.length > 0 && (
        <div className="rounded-lg border border-black/10 dark:border-white/10 p-4">
          <div className="text-xs font-medium text-black/50 dark:text-white/50 mb-3">Top users by activity</div>
          <div className="flex flex-col gap-1.5">
            {data.top_users.map((u) => (
              <div key={u.user_id} className="flex items-center justify-between text-sm">
                <span className="text-black/70 dark:text-white/70">{u.email}</span>
                <span className="text-xs text-black/40 dark:text-white/40">
                  {u.conversation_count} chats &middot; {u.message_count} messages &middot;{" "}
                  {u.token_count.toLocaleString()} tokens
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
