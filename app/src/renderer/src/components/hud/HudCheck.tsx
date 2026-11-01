import {
  type Box,
  DEFAULT_HUD_REGIONS,
  HUD_REGION_KEYS,
  type HudCheckResult,
  type HudRegionKey,
  type HudRegions,
} from "@shared/protocol";
import { Camera, CircleCheck, CircleHelp, ImageUp, RotateCcw, Save } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { EngineError } from "@/lib/engineClient";
import { useEngine } from "@/lib/engineContext";

type Side = "left" | "right";
type Props = {
  regions: HudRegions;
  side: Side;
  inGameName?: string;
  onSave: (regions: HudRegions, side: Side) => void;
};

const LABELS: Record<HudRegionKey, string> = {
  killfeed: "Kill feed",
  timer: "Timer",
  score_left: "Score (left)",
  score_right: "Score (right)",
  health: "Health",
  centre: "Centre",
};
const READER_LABELS: Record<string, string> = { ...LABELS };
const MIN = 0.01;

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

/** Screenshot + draggable boxes: the player shows SiegeSense where their HUD is. */
export function HudCheck({ regions: initial, side: initialSide, inGameName, onSave }: Props) {
  const engine = useEngine();
  const [regions, setRegions] = useState<HudRegions>(initial);
  const [side, setSide] = useState<Side>(initialSide);
  const [result, setResult] = useState<HudCheckResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ key: HudRegionKey; mode: "move" | "resize"; x: number; y: number; start: Box } | null>(null);

  async function run(type: "hud_check" | "hud_check_file", extra: object = {}) {
    setBusy(true);
    setError(null);
    try {
      setResult(
        await engine.request<HudCheckResult>(type, {
          regions,
          my_score_side: side,
          in_game_name: inGameName,
          ...extra,
        }),
      );
    } catch (err) {
      setError(err instanceof EngineError ? err.message : "Could not read the HUD.");
    } finally {
      setBusy(false);
    }
  }

  async function loadImage() {
    const path = await window.siegesense?.pickFile([{ name: "Screenshots", extensions: ["png", "jpg", "jpeg", "bmp"] }]);
    if (path) await run("hud_check_file", { path });
  }

  function onPointerDown(e: React.PointerEvent, key: HudRegionKey, mode: "move" | "resize") {
    e.stopPropagation();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    drag.current = { key, mode, x: e.clientX, y: e.clientY, start: regions[key] };
  }

  function onPointerMove(e: React.PointerEvent) {
    const d = drag.current;
    const rect = stageRef.current?.getBoundingClientRect();
    if (!d || !rect || !rect.width || !rect.height) return;
    const dx = (e.clientX - d.x) / rect.width;
    const dy = (e.clientY - d.y) / rect.height;
    const s = d.start;
    const next: Box =
      d.mode === "move"
        ? { ...s, x: clamp(s.x + dx, 0, 1 - s.w), y: clamp(s.y + dy, 0, 1 - s.h) }
        : { ...s, w: clamp(s.w + dx, MIN, 1 - s.x), h: clamp(s.h + dy, MIN, 1 - s.y) };
    setRegions((r) => ({ ...r, [d.key]: next }));
  }

  function onPointerUp() {
    drag.current = null;
  }

  const pct = (v: number) => `${(v * 100).toFixed(3)}%`;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="primary" icon={Camera} loading={busy} onClick={() => run("hud_check")}>
          Take screenshot
        </Button>
        <Button icon={ImageUp} onClick={loadImage} disabled={busy}>
          Load image…
        </Button>
        <Button variant="ghost" icon={RotateCcw} onClick={() => setRegions(DEFAULT_HUD_REGIONS)}>
          Reset to defaults
        </Button>
        <div role="radiogroup" aria-label="My score is on the" className="ml-auto flex items-center gap-2 text-sm">
          <span className="text-muted">My score is on the</span>
          <div className="flex rounded-lg bg-surface-2 p-0.5">
            {(["left", "right"] as const).map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={side === s}
                onClick={() => setSide(s)}
                className={cn("h-7 rounded-md px-3 text-xs capitalize", side === s ? "bg-surface text-text shadow" : "text-muted")}
              >
                {s === "left" ? "Left" : "Right"}
              </button>
            ))}
          </div>
        </div>
      </div>
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}

      <div className="grid grid-cols-[1fr_240px] gap-4">
        <div
          ref={stageRef}
          data-testid="hud-stage"
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          // The stage takes the screenshot's own shape (ultrawide, 16:10, 4:3 stretched…) so the
          // normalised boxes sit on exactly the pixels the engine reads.
          style={{ aspectRatio: result ? `${result.width} / ${result.height}` : "16 / 9" }}
          className="relative w-full overflow-hidden rounded-xl border border-border bg-surface-2"
        >
          {result ? (
            <img
              src={`data:image/jpeg;base64,${result.image_jpeg_b64}`}
              alt="Screenshot of your game"
              className="pointer-events-none absolute inset-0 h-full w-full"
              draggable={false}
            />
          ) : (
            <p className="absolute inset-0 flex items-center justify-center px-8 text-center text-sm text-muted">
              Open Siege (any match or the Shooting Range), then take a screenshot. Drag the boxes onto your HUD.
            </p>
          )}
          {HUD_REGION_KEYS.map((key) => {
            const b = regions[key];
            return (
              <div
                key={key}
                data-testid={`box-${key}`}
                onPointerDown={(e) => onPointerDown(e, key, "move")}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                className="absolute cursor-move touch-none rounded-sm border-2 border-accent bg-accent/10"
                style={{ left: pct(b.x), top: pct(b.y), width: pct(b.w), height: pct(b.h) }}
              >
                <span className="pointer-events-none absolute -top-5 left-0 whitespace-nowrap rounded bg-accent px-1 text-[10px] font-semibold text-bg">
                  {LABELS[key]}
                </span>
                <span
                  data-testid={`resize-${key}`}
                  onPointerDown={(e) => onPointerDown(e, key, "resize")}
                  onPointerMove={onPointerMove}
                  onPointerUp={onPointerUp}
                  className="absolute -bottom-1.5 -right-1.5 size-3 cursor-nwse-resize rounded-sm border border-bg bg-accent"
                />
              </div>
            );
          })}
        </div>

        <aside className="flex flex-col gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">What SiegeSense read</p>
          {result ? (
            <ul data-testid="hud-readings" className="flex flex-col gap-1.5">
              {result.readers.map((r) => (
                <li key={r.key} className="rounded-lg bg-surface-2 px-3 py-2">
                  <p className="flex items-center gap-1.5 text-xs text-muted">
                    {r.ok ? <CircleCheck className="size-3.5 text-ok" /> : <CircleHelp className="size-3.5 text-warn" />}
                    {READER_LABELS[r.key] ?? r.key}
                  </p>
                  <p className="mt-0.5 truncate font-mono text-sm">{r.text || "—"}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">Nothing yet. Take a screenshot to check.</p>
          )}
          <p className="mt-auto text-xs text-muted">Moved a box? Take another screenshot to re-check.</p>
        </aside>
      </div>

      <div className="flex justify-end">
        <Button variant="primary" icon={Save} onClick={() => onSave(regions, side)}>
          Save HUD layout
        </Button>
      </div>
    </div>
  );
}
