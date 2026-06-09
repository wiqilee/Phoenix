import { cn } from "@/lib/cn";

const STEP_STYLES: Record<string, string> = {
  PERCEIVE: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  DIAGNOSE: "bg-purple-500/10 text-purple-400 border-purple-500/30",
  STRATEGIZE: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  EXECUTE: "bg-phoenix-500/10 text-phoenix-400 border-phoenix-500/30",
  VERIFY: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30",
  DECIDE: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  MEMORY: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30",
  ERROR: "bg-red-500/10 text-red-400 border-red-500/30",
  ESCALATE: "bg-orange-500/10 text-orange-400 border-orange-500/30",
  INFO: "bg-ink-700 text-ink-300 border-ink-600",
};

export function StepBadge({ step }: { step: string }) {
  const style = STEP_STYLES[step] ?? STEP_STYLES.INFO;
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider border",
        style,
      )}
    >
      {step}
    </span>
  );
}
