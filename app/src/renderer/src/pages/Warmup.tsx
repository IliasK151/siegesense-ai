import type { HistoryPoint, WarmupSummary } from "@shared/protocol";
import { Crosshair, Square } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FlickChart } from "@/components/warmup/FlickChart";
import { FlickList } from "@/components/warmup/FlickList";
import { fmtElapsed, pct } from "@/components/warmup/format";
import { MetricTile } from "@/components/warmup/MetricTile";
import { Sparkline } from "@/components/warmup/Sparkline";
import { WarmupSummaryView } from "@/components/warmup/WarmupSummaryView";
import { EngineError } from "@/lib/engineClient";
import { useEngine, useProfile } from "@/lib/engineContext";
import { useWarmup } from "@/store/warmup";
import { PageHeader } from "./PageHeader";

const setOverlay = (visible: boolean) => window.siegesense?.setOverlayVisible?.(visible);
const INTERRUPTED = "Your warm-up was interrupted because the engine restarted. Start a new one.";

function interrupt() {
  useWarmup.getState().set({ phase: "idle", startedAt: null, error: INTERRUPTED });
  setOverlay(false);
}

function useElapsed(startedAt: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (startedAt === null) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  return startedAt === null ? 0 : (now - startedAt) / 1000;
}

export function Warmup() {
  const engine = useEngine();
  const { profile } = useProfile();
  const w = useWarmup();
  const elapsed = useElapsed(w.phase === "running" ? w.startedAt : null);

  useEffect(() => {
    const offMetrics = engine.on("metrics", (metrics) => useWarmup.getState().set({ metrics }));
    const offFlick = engine.on("flick", (f) => useWarmup.getState().addFlick(f));
    return () => {
      offMetrics();
      offFlick();
    };
  }, [engine]);

  // An engine restart drops the running session; don't leave the UI stuck in LIVE.
  useEffect(
    () =>
      engine.onState((state) => {
        const phase = useWarmup.getState().phase;
        if (state === "reconnecting" && (phase === "running" || phase === "stopping")) interrupt();
      }),
    [engine],
  );

  useEffect(() => {
    engine
      .request<{ history: HistoryPoint[] }>("get_warmup_history")
      .then((r) => useWarmup.getState().set({ history: r.history }))
      .catch(() => {});
  }, [engine]);

  async function start() {
    w.set({ phase: "starting", error: null, metrics: null, flicks: [], summary: null });
    try {
      await engine.request("start_warmup");
      w.set({ phase: "running", startedAt: Date.now() });
      setOverlay(true);
    } catch (err) {
      w.set({ phase: "idle", error: err instanceof EngineError ? err.message : "Could not start the warm-up." });
    }
  }

  async function stop() {
    w.set({ phase: "stopping" });
    try {
      const summary = await engine.request<WarmupSummary>("stop_warmup");
      w.set({ phase: "summary", summary, history: summary.history, startedAt: null });
    } catch (err) {
      if (err instanceof EngineError && (err.code === "not_running" || err.code === "disconnected")) {
        interrupt();
        return;
      }
      w.set({ phase: "running", error: err instanceof EngineError ? err.message : "Could not stop the warm-up." });
      return;
    } finally {
      setOverlay(false);
    }
  }

  const calibrated = Boolean(profile?.counts_per_360);
  const m = w.metrics;
  const lastFlick = w.flicks[w.flicks.length - 1];
  const live = w.phase === "running" || w.phase === "stopping";

  return (
    <>
      <PageHeader
        title="Warm-up"
        subtitle="Aim training feedback from your own mouse, live."
        action={
          live ? (
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-2 rounded-full border border-error/40 bg-error/10 px-3 py-1 text-xs font-semibold text-error">
                <span className="size-2 animate-pulse rounded-full bg-error" />
                LIVE
              </span>
              <span className="font-mono text-sm text-muted">{fmtElapsed(elapsed)}</span>
              <Button icon={Square} loading={w.phase === "stopping"} onClick={stop}>
                Stop
              </Button>
            </div>
          ) : (
            <Badge tone={calibrated ? "ok" : "warn"}>{calibrated ? "Calibrated" : "Estimated — calibrate in Settings"}</Badge>
          )
        }
      />

      {(w.phase === "idle" || w.phase === "starting") && (
        <section className="relative overflow-hidden rounded-[var(--radius-card)] border border-border bg-surface p-8">
          <div className="pointer-events-none absolute -right-20 -top-20 size-72 rounded-full bg-accent/10 blur-3xl" />
          <h2 className="text-xl font-semibold">Ready to warm up?</h2>
          <p className="mt-1.5 max-w-lg text-sm text-muted">
            Load the Shooting Range or T-Hunt in Siege, then press start. Flick between targets like you normally
            would — SiegeSense measures every flick and overshoot.
          </p>
          <div className="mt-6 flex items-center gap-4">
            <Button variant="primary" size="lg" icon={Crosshair} loading={w.phase === "starting"} onClick={start}>
              Start warm-up
            </Button>
            {w.error && (
              <p role="alert" className="text-sm text-error">
                {w.error}
              </p>
            )}
          </div>
          <div className="mt-8">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Recent scores</p>
            <Sparkline points={w.history} />
          </div>
        </section>
      )}

      {live && (
        <div className="flex flex-col gap-5">
          <div className="grid grid-cols-4 grid-rows-2 gap-4">
            <MetricTile
              big
              tone="accent"
              label="Score"
              value={m?.score ?? "—"}
              hint={m?.score === null || !m ? "Needs 5 flicks" : undefined}
              testId="tile-score"
            />
            <MetricTile label="Flicks" value={m?.flicks ?? 0} testId="tile-flicks" />
            <MetricTile label="Overshoot" value={pct(m?.overshoot_rate ?? 0)} testId="tile-overshoot" />
            <MetricTile label="Corrections" value={pct(m?.correction_rate ?? 0)} testId="tile-corrections" />
            <MetricTile label="Avg flick speed" value={`${Math.round(m?.avg_peak_speed ?? 0)}°/s`} />
            <MetricTile label="Shots while moving" value={pct(m?.moving_shot_rate ?? 0)} />
            <MetricTile label="ADS jitter" value={`${(m?.ads_jitter_per_s ?? 0).toFixed(1)}/s`} />
          </div>
          <div className="grid grid-cols-5 gap-5">
            <Card title="Last flick" className="col-span-3">
              {lastFlick ? (
                <FlickChart flick={lastFlick} />
              ) : (
                <p className="py-12 text-center text-sm text-muted">Waiting for your first flick…</p>
              )}
            </Card>
            <Card title="Recent flicks" className="col-span-2">
              <FlickList flicks={w.flicks} />
            </Card>
          </div>
          {w.error && (
            <p role="alert" className="text-sm text-error">
              {w.error}
            </p>
          )}
        </div>
      )}

      {w.phase === "summary" && w.summary && (
        <WarmupSummaryView summary={w.summary} onAgain={() => w.set({ phase: "idle", summary: null, flicks: [], metrics: null })} />
      )}
    </>
  );
}
