import type { Flick, HistoryPoint, WarmupMetrics, WarmupSummary } from "@shared/protocol";
import { create } from "zustand";

export type WarmupPhase = "idle" | "starting" | "running" | "stopping" | "summary";

type WarmupState = {
  phase: WarmupPhase;
  startedAt: number | null;
  metrics: WarmupMetrics | null;
  flicks: Flick[];
  summary: WarmupSummary | null;
  history: HistoryPoint[];
  error: string | null;
  set: (patch: Partial<Omit<WarmupState, "set" | "reset" | "addFlick">>) => void;
  addFlick: (f: Flick) => void;
  reset: () => void;
};

const initial = {
  phase: "idle" as WarmupPhase,
  startedAt: null,
  metrics: null,
  flicks: [],
  summary: null,
  history: [],
  error: null,
};

/** Warm-up state lives outside the page so navigating away and back keeps the live view. */
export const useWarmup = create<WarmupState>((set) => ({
  ...initial,
  set: (patch) => set(patch),
  addFlick: (f) => set((s) => ({ flicks: [...s.flicks, f].slice(-50) })),
  reset: () => set(initial),
}));
