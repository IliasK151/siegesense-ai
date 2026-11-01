import { Crosshair, ShieldCheck, Sparkles } from "lucide-react";
import { LogoMark } from "@/components/shell/TitleBar";

const points = [
  { icon: Crosshair, title: "Reads your mechanics", text: "Flicks, overshoot and reaction time from your own mouse." },
  { icon: Sparkles, title: "Coaches between rounds", text: "Short, specific tips when you die or the round ends." },
  { icon: ShieldCheck, title: "Fair play, always", text: "It only sees your screen and your own mouse — it never touches the game." },
];

export function StepWelcome() {
  return (
    <div>
      <LogoMark className="size-10 text-accent" />
      <h1 className="mt-5 text-3xl font-semibold tracking-tight">Welcome to SiegeSense</h1>
      <p className="mt-2 text-sm text-muted">Two minutes of setup so the coach understands your settings.</p>
      <ul className="mt-8 flex flex-col gap-3">
        {points.map(({ icon: Icon, title, text }) => (
          <li key={title} className="flex items-start gap-3.5 rounded-xl border border-border bg-surface-2/60 p-4">
            <Icon className="mt-0.5 size-4 shrink-0 text-accent" />
            <div>
              <p className="text-sm font-medium">{title}</p>
              <p className="text-xs text-muted">{text}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
