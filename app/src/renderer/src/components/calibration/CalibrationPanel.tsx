import type { CalibrationState } from "@shared/protocol";
import { CircleCheck, Keyboard, RotateCcw, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { fmtInt } from "@/lib/aim";
import { cn } from "@/lib/cn";
import { EngineError } from "@/lib/engineClient";
import { useEngine } from "@/lib/engineContext";

type Props = { onResult: (counts: number) => void; onCancel?: () => void; dpi?: number };

const STEPS = [
  "Switch to Siege (the Shooting Range is ideal) and aim at a sharp edge.",
  "Press F8, turn exactly one full circle to the right, stop on the same edge, press F8.",
  "Do it 3 times. Move slowly and smoothly — accuracy matters, not speed.",
];

export function CalibrationPanel({ onResult, onCancel, dpi }: Props) {
  const engine = useEngine();
  const [state, setState] = useState<CalibrationState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => engine.on("calibration", setState), [engine]);

  // Leaving the panel mid-calibration releases the player's input in the engine.
  const activeRef = useRef(false);
  activeRef.current = state?.phase === "armed" || state?.phase === "measuring";
  useEffect(
    () => () => {
      if (activeRef.current) engine.request("cancel_calibration").catch(() => {});
    },
    [engine],
  );

  async function start() {
    setBusy(true);
    setError(null);
    try {
      setState(await engine.request<CalibrationState>("start_calibration"));
    } catch (err) {
      setError(err instanceof EngineError ? err.message : "Could not start calibration.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    await engine.request("cancel_calibration").catch(() => {});
    setState(null);
    onCancel?.();
  }

  const running = state && (state.phase === "armed" || state.phase === "measuring");
  const done = state?.phase === "done" && state.result !== null;

  return (
    <div className="rounded-xl border border-border bg-surface-2/60 p-5">
      <ol className="flex flex-col gap-2.5">
        {STEPS.map((text, i) => (
          <li key={text} className="flex gap-3 text-sm">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full border border-accent/50 text-[11px] font-semibold text-accent">
              {i + 1}
            </span>
            <span className="text-muted">{text}</span>
          </li>
        ))}
      </ol>

      {!running && !done && (
        <div className="mt-5 flex items-center gap-3">
          <Button variant="primary" icon={Keyboard} loading={busy} onClick={start}>
            Start calibration
          </Button>
          {error && (
            <p role="alert" className="text-xs text-error">
              {error}
            </p>
          )}
        </div>
      )}

      {running && state && (
        <div className="mt-5">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.12em] text-muted">
                Run {Math.min(state.runs.length + 1, state.target_runs)} of {state.target_runs}
              </p>
              <p className="mt-1 text-sm">
                {state.phase === "measuring" ? (
                  <span className="text-accent">Turning… press F8 when you're back on the edge.</span>
                ) : (
                  <span>Press F8 in Siege to begin this run.</span>
                )}
              </p>
            </div>
            <p data-testid="live-counts" className="font-mono text-3xl font-semibold tabular-nums">
              {fmtInt(state.current_counts)}
            </p>
          </div>
          <RunChips runs={state.runs} target={state.target_runs} />
          {state.warning && <Warning text={state.warning} />}
          <div className="mt-4">
            <Button variant="ghost" size="sm" onClick={cancel}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {done && state && state.result !== null && (
        <div className="mt-5">
          <p className="flex items-center gap-2 text-sm font-medium text-ok">
            <CircleCheck className="size-4" /> {fmtInt(state.result)} counts per 360°
            {dpi ? <span className="text-muted">· {((state.result / dpi) * 2.54).toFixed(1)} cm/360</span> : null}
          </p>
          <RunChips runs={state.runs} target={state.target_runs} />
          {state.warning && <Warning text={state.warning} />}
          <div className="mt-4 flex gap-2">
            <Button variant="primary" onClick={() => onResult(state.result!)}>
              Use this result
            </Button>
            <Button icon={RotateCcw} onClick={start}>
              Redo
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function RunChips({ runs, target }: { runs: number[]; target: number }) {
  return (
    <div className="mt-3 flex gap-2">
      {Array.from({ length: target }, (_, i) => (
        <span
          key={i}
          className={cn(
            "rounded-lg border px-2.5 py-1 font-mono text-xs",
            runs[i] !== undefined ? "border-accent/40 bg-accent/10 text-text" : "border-border text-muted",
          )}
        >
          {runs[i] !== undefined ? fmtInt(runs[i]!) : `Run ${i + 1}`}
        </span>
      ))}
    </div>
  );
}

function Warning({ text }: { text: string }) {
  return (
    <p role="status" className="mt-3 flex items-start gap-2 text-xs text-warn">
      <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
      {text}
    </p>
  );
}
