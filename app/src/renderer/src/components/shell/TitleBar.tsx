export function LogoMark({ className = "size-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M12 2 3 6v6c0 5 3.8 9.3 9 10 5.2-.7 9-5 9-10V6z" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="12" cy="12" r="3.2" fill="currentColor" />
      <path d="M12 6.5v2.3M12 15.2v2.3M6.5 12h2.3M15.2 12h2.3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function TitleBar() {
  return (
    <div className="drag flex h-10 shrink-0 items-center gap-2 border-b border-border/60 bg-bg pl-4 pr-36">
      <LogoMark className="size-4 text-accent" />
      <span className="text-[13px] font-semibold tracking-tight">
        Siege<span className="text-accent">Sense</span>
      </span>
    </div>
  );
}
