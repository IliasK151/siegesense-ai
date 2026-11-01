import type { MatchSummary } from "@shared/protocol";
import { Radio, Square } from "lucide-react";
import { useEffect, useState } from "react";
import { DeathCard } from "@/components/live/DeathCard";
import { EventFeed } from "@/components/live/EventFeed";
import { MatchSummaryView } from "@/components/live/MatchSummaryView";
import { RoundStrip } from "@/components/live/RoundStrip";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusLight } from "@/components/ui/StatusLight";
import { fmtElapsed } from "@/components/warmup/format";
import { EngineError } from "@/lib/engineClient";
import { useEngine, useStatus } from "@/lib/engineContext";
import { useLive } from "@/store/live";
import { PageHeader } from "./PageHeader";

const CHECKLIST = ["game", "capture", "hud", "input"] as const;
const INTERRUPTED = "Live Mode stopped because the engine restarted. Start it again.";

function useElapsed(startedAt: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (startedAt === null) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  return startedAt === null ? 0 : (now - startedAt) / 1000;
}

export function Live() {
  const engine = useEngine();
  const status = useStatus();
  const live = useLive();
  const elapsed = useElapsed(live.phase === "running" ? live.startedAt : null);

  useEffect(() => {
    const offEvent = engine.on("live_event", (e) => useLive.getState().addEvent(e));
    const offRound = engine.on("round_summary", (r) => useLive.getState().putRound(r));
    const offState = engine.onState((s) => {
      const phase = useLive.getState().phase;
      if (s === "reconnecting" && (phase === "running" || phase === "stopping")) {
        useLive.getState().set({ phase: "idle", startedAt: null, error: INTERRUPTED });
      }
    });
    return () => {
      offEvent();
      offRound();
      offState();
    };
  }, [engine]);

  async function start() {
    live.set({ phase: "starting", error: null, events: [], rounds: {}, summary: null });
    try {
      await engine.request("start_live");
      live.set({ phase: "running", startedAt: Date.now() });
    } catch (err) {
      live.set({ phase: "idle", error: err instanceof EngineError ? err.message : "Could not start Live Mode." });
    }
  }

  async function stop() {
    live.set({ phase: "stopping" });
    try {
      const summary = await engine.request<MatchSummary>("stop_live");
      live.set({ phase: "summary", summary, startedAt: null });
    } catch (err) {
      if (err instanceof EngineError && (err.code === "not_running" || err.code === "disconnected")) {
        live.set({ phase: "idle", startedAt: null, error: INTERRUPTED });
      } else {
        live.set({ phase: "running", error: err instanceof EngineError ? err.message : "Could not stop Live Mode." });
      }
    }
  }

  const rounds = Object.values(live.rounds).sort((a, b) => a.number - b.number);
  const deaths = live.events.filter((e) => e.kind === "death").reverse();
  const running = live.phase === "running" || live.phase === "stopping";

  return (
    <>
      <PageHeader
        title="Live Mode"
        subtitle="Play ranked as usual — the coach watches and records your deaths."
        action={
          running && (
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-2 rounded-full border border-error/40 bg-error/10 px-3 py-1 text-xs font-semibold text-error">
                <span className="size-2 animate-pulse rounded-full bg-error" />
                LIVE
              </span>
              <span className="font-mono text-sm text-muted">{fmtElapsed(elapsed)}</span>
              <Button icon={Square} loading={live.phase === "stopping"} onClick={stop}>
                Stop
              </Button>
            </div>
          )
        }
      />

      {(live.phase === "idle" || live.phase === "starting") && (
        <section className="relative overflow-hidden rounded-[var(--radius-card)] border border-border bg-surface p-8">
          <div className="pointer-events-none absolute -right-20 -top-20 size-72 rounded-full bg-accent/10 blur-3xl" />
          <h2 className="text-xl font-semibold">Ready for ranked?</h2>
          <p className="mt-1.5 max-w-lg text-sm text-muted">
            Start Live Mode, then play. SiegeSense reads your HUD, tracks every round and saves a clip of each death so
            you can see what happened. Nothing is shown in game mid-round.
          </p>
          <ul data-testid="live-checklist" className="mt-6 grid max-w-xl grid-cols-2 gap-3">
            {CHECKLIST.map((k) =>
              status ? (
                <li key={k} className="rounded-xl border border-border bg-surface-2/60 px-3 py-2.5">
                  <StatusLight lightKey={k} light={status.lights[k]} />
                </li>
              ) : null,
            )}
          </ul>
          <div className="mt-6 flex items-center gap-4">
            <Button variant="primary" size="lg" icon={Radio} loading={live.phase === "starting"} onClick={start}>
              Start Live Mode
            </Button>
            {live.error && (
              <p role="alert" className="text-sm text-error">
                {live.error}
              </p>
            )}
          </div>
        </section>
      )}

      {running && (
        <div className="flex flex-col gap-5">
          <Card title="Rounds">
            <RoundStrip rounds={rounds} />
          </Card>
          <div className="grid grid-cols-5 gap-5">
            <div className="col-span-3 flex flex-col gap-4">
              {deaths.length ? (
                deaths.map((e) => <DeathCard key={`${e.t}`} event={e} round={live.rounds[e.round]} />)
              ) : (
                <Card title="Deaths">
                  <p className="py-10 text-center text-sm text-muted">
                    No deaths yet. Each death gets a clip of the 10 seconds before it.
                  </p>
                </Card>
              )}
            </div>
            <Card title="Live feed" className="col-span-2">
              <EventFeed events={live.events} />
            </Card>
          </div>
          {live.error && (
            <p role="alert" className="text-sm text-error">
              {live.error}
            </p>
          )}
        </div>
      )}

      {live.phase === "summary" && live.summary && (
        <MatchSummaryView summary={live.summary} onAgain={() => live.set({ phase: "idle", summary: null })} />
      )}
    </>
  );
}
