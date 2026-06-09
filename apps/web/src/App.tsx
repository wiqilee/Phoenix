import { Flame, Github, Trash2 } from "lucide-react";

import { useAgentStream } from "@/hooks/useAgentStream";
import { ConnectionPill } from "@/components/ConnectionPill";
import { ReasoningTrace } from "@/components/ReasoningTrace";
import { StatsBar } from "@/components/StatsBar";

export default function App() {
  const { events, status, reconnect, clear } = useAgentStream();

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-ink-700 bg-ink-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-phoenix-500 to-phoenix-700 flex items-center justify-center">
              <Flame className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg text-ink-100">Phoenix</h1>
              <p className="text-[11px] text-ink-500">
                Autonomous GitLab pipeline repair
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <ConnectionPill status={status} onReconnect={reconnect} />
            <a
              href="https://github.com/wiqi-lee/phoenix"
              target="_blank"
              rel="noreferrer"
              className="text-ink-500 hover:text-ink-300 transition"
              aria-label="GitHub"
            >
              <Github className="w-5 h-5" />
            </a>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-6 space-y-6">
        <StatsBar events={events} />

        <section className="rounded-xl border border-ink-700 bg-ink-800/30 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-ink-700">
            <h2 className="text-sm font-semibold text-ink-200 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-phoenix-500 animate-pulse-fast" />
              Agent Activity Feed
            </h2>
            {events.length > 0 && (
              <button
                onClick={clear}
                className="text-xs text-ink-500 hover:text-ink-300 transition flex items-center gap-1"
              >
                <Trash2 className="w-3 h-3" />
                Clear
              </button>
            )}
          </div>
          <ReasoningTrace events={events} />
        </section>

        <p className="text-center text-xs text-ink-600 pt-4">
          Built by{" "}
          <a
            href="https://x.com/wiqi_lee"
            target="_blank"
            rel="noreferrer"
            className="text-phoenix-400 hover:text-phoenix-300"
          >
            @wiqi_lee
          </a>{" "}
          for the Google Cloud Rapid Agent Hackathon 2026.
        </p>
      </main>
    </div>
  );
}
