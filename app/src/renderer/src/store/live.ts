import type { LiveEvent, MatchSummary, RoundSummary } from "@shared/protocol";
import { create } from "zustand";

export type LivePhase = "idle" | "starting" | "running" | "stopping" | "summary";

type LiveState = {
  phase: LivePhase;
  startedAt: number | null;
  events: LiveEvent[];
  rounds: Record<number, RoundSummary>;
  summary: MatchSummary | null;
  error: string | null;
  set: (patch: Partial<Omit<LiveState, "set" | "reset" | "addEvent" | "putRound">>) => void;
  addEvent: (e: LiveEvent) => void;
  putRound: (r: RoundSummary) => void;
  reset: () => void;
};

const initial = { phase: "idle" as LivePhase, startedAt: null, events: [], rounds: {}, summary: null, error: null };

export const useLive = create<LiveState>((set) => ({
  ...initial,
  set: (patch) => set(patch),
  addEvent: (e) => set((s) => ({ events: [...s.events, e].slice(-200) })),
  putRound: (r) => set((s) => ({ rounds: { ...s.rounds, [r.number]: r } })),
  reset: () => set(initial),
}));
