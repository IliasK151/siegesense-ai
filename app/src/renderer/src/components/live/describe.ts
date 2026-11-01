import type { LiveEvent } from "@shared/protocol";

/** One line of plain-language text for a live event. Only the player's own events are shown. */
export function describeEvent(e: LiveEvent): string {
  const d = e.data as Record<string, unknown>;
  switch (e.kind) {
    case "round_start":
      return `Round ${e.round} started`;
    case "phase":
      return d.phase === "prep" ? "Preparation phase" : "Action phase";
    case "kill":
      return `You eliminated ${String(d.victim ?? "an enemy")}${d.first_blood ? " — first blood" : ""}${d.trade ? " (trade)" : ""}`;
    case "death":
      return `You died${d.killer ? ` — killed by ${String(d.killer)}` : ""}`;
    case "round_end":
      return d.result === "win" ? `Round ${e.round} won` : d.result === "loss" ? `Round ${e.round} lost` : `Round ${e.round} over`;
    case "repeek":
      return `Re-peeked the same angle ${Number(d.seconds_after_kill ?? 0).toFixed(1)} s after a kill`;
  }
}
