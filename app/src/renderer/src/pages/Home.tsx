import { LIGHT_KEYS } from "@shared/protocol";
import { Crosshair, Pencil, Radio } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusLight } from "@/components/ui/StatusLight";
import { useProfile, useStatus } from "@/lib/engineContext";
import { useNav } from "@/store/nav";
import { ProfileSummary } from "./ProfileSummary";


export function Home() {
  const { profile } = useProfile();
  const status = useStatus();
  const go = useNav((s) => s.go);
  return (
    <div className="flex flex-col gap-5">
      <section className="relative overflow-hidden rounded-[var(--radius-card)] border border-border bg-surface p-8">
        <div className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-accent/10 blur-3xl" />
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">Ready when you are</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          {profile ? `Let's get better, ${profile.in_game_name}.` : "Let's get better."}
        </h1>
        <p className="mt-2 max-w-lg text-sm text-muted">
          SiegeSense watches your screen and your own mouse while you play, then coaches you between rounds.
          It never touches the game.
        </p>
        <div className="mt-7 flex gap-3">
          <Button variant="primary" size="lg" icon={Radio} onClick={() => go("live")}>
            Start Live Mode
          </Button>
          <Button size="lg" icon={Crosshair} onClick={() => go("warmup")}>
            Start Warm-up
          </Button>
        </div>
      </section>

      <div className="grid grid-cols-5 gap-5">
        <Card title="System status" className="col-span-2" data-testid="status-card">
          {status ? (
            <ul className="flex flex-col gap-3">
              {LIGHT_KEYS.map((k) => (
                <li key={k} className="flex items-center justify-between gap-3">
                  <StatusLight lightKey={k} light={status.lights[k]} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">Connecting to engine…</p>
          )}
        </Card>
        <Card
          title="Your setup"
          className="col-span-3"
          action={
            <Button size="sm" variant="ghost" icon={Pencil} onClick={() => go("setup")}>
              Edit setup
            </Button>
          }
        >
          {profile && <ProfileSummary profile={profile} />}
        </Card>
      </div>
    </div>
  );
}
