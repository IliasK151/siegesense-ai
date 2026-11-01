// Starts the real Python engine against a temp data dir with a fake Documents folder.
import { type ChildProcess, spawn } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createInterface } from "node:readline";

const repo = resolve(import.meta.dirname, "../../..");

function enginePython(): string {
  if (process.env.ENGINE_PYTHON) return process.env.ENGINE_PYTHON;
  const venv = join(repo, "engine", ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  return existsSync(venv) ? venv : "python3";
}

export default async function globalSetup() {
  const tmp = mkdtempSync(join(tmpdir(), "siegesense-e2e-"));
  const docs = join(tmp, "docs");
  const settingsDir = join(docs, "My Games", "Rainbow Six - Siege", "abc");
  mkdirSync(settingsDir, { recursive: true });
  copyFileSync(join(repo, "engine/tests/fixtures/GameSettings_utf8.ini"), join(settingsDir, "GameSettings.ini"));

  const child: ChildProcess = spawn(
    enginePython(),
    ["-m", "siegesense_engine", "--token", "e2e", "--data-dir", join(tmp, "data"), "--documents-dir", docs],
    { cwd: join(repo, "engine", "src"), stdio: ["pipe", "pipe", "inherit"] },
  );

  const port = await new Promise<number>((ok, fail) => {
    const timer = setTimeout(() => fail(new Error("engine did not start")), 15_000);
    createInterface({ input: child.stdout! }).on("line", (line) => {
      const m = /^READY (\d+)$/.exec(line.trim());
      if (m) {
        clearTimeout(timer);
        ok(Number(m[1]));
      }
    });
    child.on("exit", (code) => fail(new Error(`engine exited with ${code}`)));
  });
  process.env.E2E_ENGINE_PORT = String(port);
  process.env.E2E_SETTINGS_PATH = join(settingsDir, "GameSettings.ini");

  return async () => {
    child.kill();
    rmSync(tmp, { recursive: true, force: true });
  };
}
