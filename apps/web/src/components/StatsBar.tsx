import { Brain, CheckCircle, Clock, GitMerge } from "lucide-react";

import { cn } from "@/lib/cn";
import type { AgentEvent } from "@/hooks/useAgentStream";

interface StatsBarProps {
  events: AgentEvent[];
}

export function StatsBar({ events }: StatsBarProps) {
  const decisions = events.filter(
    (e) => (e.payload?.step as string) === "DECIDE",
  );
  const mrsCreated = events.filter((e) => e.payload?.mr_iid).length;
  const avgConfidence = (() => {
    const scores = events
      .map((e) => e.payload?.confidence as number | undefined)
      .filter((c): c is number => typeof c === "number");
    if (scores.length === 0) return 0;
    return scores.reduce((a, b) => a + b, 0) / scores.length;
  })();

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <StatCard
        label="Events Streamed"
        value={events.length.toString()}
        icon={Brain}
        accent="text-blue-400"
      />
      <StatCard
        label="Decisions Made"
        value={decisions.length.toString()}
        icon={CheckCircle}
        accent="text-emerald-400"
      />
      <StatCard
        label="Merge Requests"
        value={mrsCreated.toString()}
        icon={GitMerge}
        accent="text-phoenix-400"
      />
      <StatCard
        label="Avg Confidence"
        value={`${(avgConfidence * 100).toFixed(0)}%`}
        icon={Clock}
        accent={cn(
          avgConfidence >= 0.8
            ? "text-emerald-400"
            : avgConfidence >= 0.6
              ? "text-yellow-400"
              : "text-ink-500",
        )}
      />
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  accent?: string;
}

function StatCard({ label, value, icon: Icon, accent }: StatCardProps) {
  return (
    <div className="rounded-lg border border-ink-700 bg-ink-800/50 p-4">
      <div className="flex items-center gap-2 text-ink-500 text-xs mb-2">
        <Icon className={cn("w-4 h-4", accent)} />
        <span>{label}</span>
      </div>
      <p className={cn("text-2xl font-bold font-mono", accent)}>{value}</p>
    </div>
  );
}
