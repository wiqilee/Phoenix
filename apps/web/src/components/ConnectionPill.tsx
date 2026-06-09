import { Wifi, WifiOff } from "lucide-react";

import { cn } from "@/lib/cn";

interface ConnectionPillProps {
  status: "connecting" | "open" | "closed";
  onReconnect: () => void;
}

export function ConnectionPill({ status, onReconnect }: ConnectionPillProps) {
  if (status === "open") {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium">
        <Wifi className="w-3 h-3" />
        <span>Live</span>
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-fast" />
      </div>
    );
  }
  if (status === "connecting") {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-xs font-medium">
        <Wifi className="w-3 h-3" />
        <span>Connecting</span>
      </div>
    );
  }
  return (
    <button
      onClick={onReconnect}
      className={cn(
        "inline-flex items-center gap-2 px-3 py-1 rounded-full",
        "bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-medium",
        "hover:bg-red-500/20 transition",
      )}
    >
      <WifiOff className="w-3 h-3" />
      <span>Reconnect</span>
    </button>
  );
}
