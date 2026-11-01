import { CircleAlert, LoaderCircle } from "lucide-react";
import { useConnState, useEngineState } from "@/lib/engineContext";

export function EngineBanner() {
  const conn = useConnState();
  const engine = useEngineState();
  if (engine?.phase === "failed") {
    return (
      <div role="alert" className="flex items-start gap-3 border-b border-error/30 bg-error/10 px-5 py-3 text-sm">
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-error" />
        <div className="min-w-0">
          <p className="font-semibold text-error">Engine stopped</p>
          <p className="whitespace-pre-wrap break-words text-xs text-muted">{engine.message}</p>
          <p className="mt-1 text-xs text-text">Close and reopen SiegeSense to try again.</p>
        </div>
      </div>
    );
  }
  if (conn === "reconnecting" || engine?.phase === "restarting") {
    return (
      <div role="status" className="flex items-center gap-2 border-b border-warn/30 bg-warn/10 px-5 py-2 text-xs text-warn">
        <LoaderCircle className="size-3.5 animate-spin" />
        Reconnecting to engine…
      </div>
    );
  }
  return null;
}
