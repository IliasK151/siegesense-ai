import type { Flick, WarmupMetrics } from "@shared/protocol";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { flickTag, pct } from "@/components/warmup/format";
import { cn } from "@/lib/cn";
import { EngineClient } from "@/lib/engineClient";
import type { EngineLike } from "@/lib/engineContext";

const tagColor = { ok: "text-ok", warn: "text-warn", error: "text-error" };

/** The small in-game card shown during Warm-up. Transparent window, click-through, never focused. */
export function OverlayApp({ client }: { client?: EngineLike }) {
  const engine = useMemo<EngineLike>(
    () => client ?? new EngineClient(() => window.siegesense!.getEngine()),
    [client],
  );
  const [metrics, setMetrics] = useState<WarmupMetrics | null>(null);
  const [last, setLast] = useState<Flick | null>(null);

  useEffect(() => {
    const offM = engine.on("metrics", setMetrics);
    const offF = engine.on("flick", setLast);
    engine.connect().catch(() => {});
    return () => {
      offM();
      offF();
    };
  }, [engine]);

  const tag = last ? flickTag(last) : null;
  return (
    <div className="flex h-full items-start justify-end p-1">
      <div className="w-full rounded-2xl border border-accent/40 bg-bg/80 px-4 py-3 shadow-2xl shadow-black/60 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-accent">SiegeSense · Warm-up</span>
          {tag && last && (
            <motion.span
              key={last.id}
              data-testid="overlay-tag"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className={cn("text-xs font-semibold", tagColor[tag.tone])}
            >
              {tag.label}
            </motion.span>
          )}
        </div>
        <div className="mt-2 flex items-end gap-5">
          <div>
            <p className="text-[10px] uppercase tracking-[0.12em] text-muted">Score</p>
            <p data-testid="overlay-score" className="font-mono text-4xl font-semibold leading-none text-text">
              {metrics?.score ?? "—"}
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.12em] text-muted">Overshoot</p>
            <p data-testid="overlay-overshoot" className="font-mono text-xl font-semibold">
              {pct(metrics?.overshoot_rate ?? 0)}
            </p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.12em] text-muted">Flicks</p>
            <p data-testid="overlay-flicks" className="font-mono text-xl font-semibold">
              {metrics?.flicks ?? 0}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
