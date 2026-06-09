import { format } from "date-fns";
import { Activity } from "lucide-react";

import { cn } from "@/lib/cn";
import type { AgentEvent } from "@/hooks/useAgentStream";
import { StepBadge } from "./StepBadge";

interface ReasoningTraceProps {
  events: AgentEvent[];
}

/**
 * Streams every agent reasoning step into a vertical timeline.
 * This is the visual centerpiece of the Phoenix demo.
 */
export function ReasoningTrace({ events }: ReasoningTraceProps) {
  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-ink-500 py-24">
        <Activity className="w-10 h-10 mb-3 opacity-40" />
        <p className="text-sm">Waiting for Phoenix to wake up...</p>
        <p className="text-xs mt-1 text-ink-600">
          Trigger a failing pipeline to see the agent reason in real time.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2 p-4 max-h-[600px] overflow-y-auto">
      {events.map((event, idx) => (
        <TraceLine key={idx} event={event} />
      ))}
    </div>
  );
}

function TraceLine({ event }: { event: AgentEvent }) {
  const step = (event.payload?.step as string) ?? event.type.toUpperCase();
  const message = (event.payload?.message as string) ?? "";
  const agent = (event.payload?.agent as string) ?? "";
  const toolCall = event.payload?.tool_call as { name?: string } | undefined;

  const time = format(new Date(event.receivedAt), "HH:mm:ss");

  return (
    <div
      className={cn(
        "flex items-start gap-3 px-3 py-2 rounded-md border border-ink-700",
        "bg-ink-800/50 hover:bg-ink-800 transition-colors animate-slide-up",
      )}
    >
      <span className="font-mono text-[11px] text-ink-500 mt-0.5 shrink-0">
        {time}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <StepBadge step={step} />
          {agent && (
            <span className="text-[10px] font-mono text-ink-500 uppercase">
              {agent}
            </span>
          )}
          {toolCall?.name && (
            <span className="text-[10px] font-mono text-phoenix-400">
              → {toolCall.name}()
            </span>
          )}
        </div>
        {message && (
          <p className="text-xs text-ink-300 font-mono leading-relaxed break-words">
            {message}
          </p>
        )}
        <ExtraDetails payload={event.payload} />
      </div>
    </div>
  );
}

function ExtraDetails({ payload }: { payload: Record<string, unknown> }) {
  const confidence = payload.confidence as number | undefined;
  const category = payload.category as string | undefined;
  const signature = payload.signature as string | undefined;
  const mrUrl = payload.mr_url as string | undefined;
  const mrIid = payload.mr_iid as number | undefined;

  if (!confidence && !category && !signature && !mrUrl) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-2 text-[11px] font-mono">
      {category && (
        <span className="px-2 py-0.5 bg-ink-900 rounded border border-ink-700 text-ink-400">
          category: <span className="text-ink-200">{category}</span>
        </span>
      )}
      {typeof confidence === "number" && (
        <span className="px-2 py-0.5 bg-ink-900 rounded border border-ink-700 text-ink-400">
          confidence:{" "}
          <span
            className={cn(
              confidence >= 0.8
                ? "text-emerald-400"
                : confidence >= 0.6
                  ? "text-yellow-400"
                  : "text-red-400",
            )}
          >
            {(confidence * 100).toFixed(0)}%
          </span>
        </span>
      )}
      {signature && (
        <span className="px-2 py-0.5 bg-ink-900 rounded border border-ink-700 text-ink-400">
          signature: <span className="text-ink-200">{signature}</span>
        </span>
      )}
      {mrUrl && mrIid && (
        <a
          href={mrUrl}
          target="_blank"
          rel="noreferrer"
          className="px-2 py-0.5 bg-emerald-500/10 hover:bg-emerald-500/20 rounded border border-emerald-500/30 text-emerald-400"
        >
          MR !{mrIid} →
        </a>
      )}
    </div>
  );
}
