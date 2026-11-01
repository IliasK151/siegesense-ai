import { ADS_KEYS, type AdsKey, type GameSettingsFile, type GameSettingsImport } from "@shared/protocol";
import { ChevronDown, FileSearch, FolderOpen, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { cn } from "@/lib/cn";
import { EngineError } from "@/lib/engineClient";
import { useEngine } from "@/lib/engineContext";
import { type ProfileDraft, toNumber, validateStep } from "./draft";
import { ImportBadge, type ImportInfo } from "./ImportBadge";

type Props = {
  draft: ProfileDraft;
  update: (d: ProfileDraft) => void;
  importInfo: ImportInfo | null;
  onImported: (result: GameSettingsImport) => void;
};

const fmtDate = (s: number) =>
  new Date(s * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

export function StepSensitivity({ draft, update, importInfo, onImported }: Props) {
  const engine = useEngine();
  const [files, setFiles] = useState<GameSettingsFile[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [adsOpen, setAdsOpen] = useState(false);
  const errors = validateStep("sensitivity", draft);
  const ads = draft.ads_sensitivity ?? {};

  useEffect(() => {
    engine
      .request<{ files: GameSettingsFile[] }>("find_game_settings")
      .then((r) => {
        setFiles(r.files);
        setSelected(r.files[0]?.path ?? null);
      })
      .catch(() => setFiles([]));
  }, [engine]);

  async function runImport(path: string) {
    setBusy(true);
    setImportError(null);
    try {
      onImported(await engine.request<GameSettingsImport>("import_game_settings", { path }));
    } catch (err) {
      setImportError(err instanceof EngineError ? err.message : "Could not read that file.");
    } finally {
      setBusy(false);
    }
  }

  async function browse() {
    const path = await window.siegesense?.pickFile([{ name: "Siege settings", extensions: ["ini"] }]);
    if (path) await runImport(path);
  }

  const num = (field: "dpi" | "yaw_sensitivity" | "pitch_sensitivity") => ({
    type: "number" as const,
    inputMode: "numeric" as const,
    value: draft[field] ?? "",
    error: errors[field],
    badge: <ImportBadge field={field} info={importInfo} />,
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => update({ [field]: toNumber(e.target.value) }),
  });

  const setAds = (key: AdsKey, raw: string) => {
    const nextAds = { ...ads };
    const value = toNumber(raw);
    if (value === undefined) delete nextAds[key];
    else nextAds[key] = value;
    update({ ads_sensitivity: nextAds });
  };

  const edpi = draft.dpi && draft.yaw_sensitivity ? draft.dpi * draft.yaw_sensitivity : null;

  return (
    <div>
      <h1 className="text-2xl font-semibold tracking-tight">Sensitivity</h1>
      <p className="mt-1.5 text-sm text-muted">
        Import your Siege settings so aim is measured in real in-game degrees.
      </p>

      <div className="mt-6 rounded-xl border border-border bg-surface-2/60 p-4">
        {files === null ? (
          <p className="flex items-center gap-2 text-sm text-muted">
            <LoaderCircle className="size-4 animate-spin" /> Looking for your Siege settings…
          </p>
        ) : files.length > 0 ? (
          <>
            <p className="flex items-center gap-2 text-sm font-medium">
              <FileSearch className="size-4 text-accent" /> Found your Siege settings
            </p>
            <ul className="mt-3 flex flex-col gap-2">
              {files.map((f) => (
                <li key={f.path}>
                  <button
                    type="button"
                    onClick={() => setSelected(f.path)}
                    aria-pressed={selected === f.path}
                    className={cn(
                      "w-full rounded-lg border px-3 py-2 text-left transition-colors duration-[var(--duration-fast)]",
                      selected === f.path ? "border-accent bg-accent/5" : "border-border hover:border-muted/50",
                    )}
                  >
                    <span className="block truncate font-mono text-xs">{f.path}</span>
                    <span className="text-[11px] text-muted">Last changed {fmtDate(f.modified)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="text-sm text-muted">
            We couldn't find GameSettings.ini automatically. Browse for it, or enter your values below.
          </p>
        )}
        <div className="mt-3 flex gap-2">
          {files && files.length > 0 && (
            <Button variant="primary" size="sm" loading={busy} disabled={!selected} onClick={() => selected && runImport(selected)}>
              Import
            </Button>
          )}
          <Button size="sm" icon={FolderOpen} onClick={browse} disabled={busy}>
            Browse…
          </Button>
        </div>
        {importError && (
          <p role="alert" className="mt-2 text-xs text-error">
            {importError}
          </p>
        )}
      </div>

      <div className="mt-6 grid grid-cols-3 gap-4">
        <Field label="Mouse DPI" placeholder="800" hint="Check your mouse software" {...num("dpi")} />
        <Field label="Horizontal sensitivity" {...num("yaw_sensitivity")} />
        <Field label="Vertical sensitivity" {...num("pitch_sensitivity")} />
      </div>

      <div className="mt-4 flex items-center justify-between rounded-xl bg-surface-2/60 px-4 py-3">
        <span className="text-xs uppercase tracking-[0.12em] text-muted">eDPI</span>
        <span data-testid="draft-edpi" className="font-mono text-lg font-semibold">
          {edpi ?? "—"}
        </span>
      </div>

      <div className="mt-4 rounded-xl border border-border">
        <button
          type="button"
          onClick={() => setAdsOpen((o) => !o)}
          aria-expanded={adsOpen}
          className="flex w-full items-center justify-between px-4 py-3 text-sm"
        >
          <span className="flex items-center gap-2">
            Scopes (ADS) <ImportBadge field="ads_sensitivity" info={importInfo} />
          </span>
          <ChevronDown className={cn("size-4 text-muted transition-transform", adsOpen && "rotate-180")} />
        </button>
        {adsOpen && (
          <div className="grid grid-cols-3 gap-3 border-t border-border p-4">
            {ADS_KEYS.map((k) => (
              <Field
                key={k}
                label={`${k} scope`}
                type="number"
                value={ads[k] ?? ""}
                onChange={(e) => setAds(k, e.target.value)}
              />
            ))}
            {errors.ads_sensitivity && (
              <p role="alert" className="col-span-3 text-xs text-error">
                {errors.ads_sensitivity}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
