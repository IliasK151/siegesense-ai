// Starts the Python engine, waits for its READY line and restarts it once if it crashes.
import { type ChildProcess, spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { EventEmitter } from "node:events";
import { join, resolve } from "node:path";
import { createInterface } from "node:readline";
import type { EngineConnection, EngineState } from "../preload/api";

export type EngineCommand = { command: string; args: string[]; cwd?: string };
export type { EngineConnection, EngineState } from "../preload/api";

const STDERR_LINES = 20;
const MAX_RESTARTS = 1;

export function resolveEngineCommand(
  opts: { isPackaged: boolean; resourcesPath: string; appRoot: string },
  platform: NodeJS.Platform = process.platform,
): EngineCommand {
  if (opts.isPackaged) {
    return { command: join(opts.resourcesPath, "engine", "siegesense-engine.exe"), args: [] };
  }
  const cwd = resolve(opts.appRoot, "..", "engine", "src");
  const module = ["-m", "siegesense_engine"];
  return platform === "win32"
    ? { command: "py", args: ["-3", ...module], cwd }
    : { command: "python3", args: module, cwd };
}

export function parseReadyLine(line: string): number | null {
  const match = /^READY (\d+)\s*$/.exec(line);
  return match ? Number(match[1]) : null;
}

type Options = { dataDir: string; startTimeoutMs?: number; spawnFn?: typeof spawn };

export class EngineSupervisor extends EventEmitter {
  connection: EngineConnection | null = null;
  private child: ChildProcess | null = null;
  private stderr: string[] = [];
  private restarts = 0;
  private stopping = false;
  private readonly startTimeoutMs: number;
  private readonly spawnFn: typeof spawn;

  constructor(
    private readonly cmd: EngineCommand,
    private readonly opts: Options,
  ) {
    super();
    this.startTimeoutMs = opts.startTimeoutMs ?? 15_000;
    this.spawnFn = opts.spawnFn ?? spawn;
  }

  start(): Promise<EngineConnection> {
    this.stopping = false;
    this.setState({ phase: "starting" });
    return this.launch().catch((err: Error) => {
      this.fail(err.message);
      throw err;
    });
  }

  /** Ask the engine to exit by closing its stdin; force-kill only if it hangs. */
  stop(graceMs = 2000): void {
    this.stopping = true;
    this.connection = null;
    const child = this.child;
    this.child = null;
    if (!child) return;
    let exited = false;
    child.once("exit", () => {
      exited = true;
    });
    child.stdin?.end();
    const timer = setTimeout(() => {
      if (!exited) child.kill();
    }, graceMs);
    timer.unref?.();
  }

  private setState(state: EngineState): void {
    this.emit("state", state);
  }

  private fail(message: string): void {
    this.connection = null;
    this.setState({ phase: "failed", message });
  }

  private stderrTail(): string {
    return this.stderr.join("\n");
  }

  private launch(): Promise<EngineConnection> {
    const token = randomBytes(24).toString("hex");
    const args = [...this.cmd.args, "--token", token, "--data-dir", this.opts.dataDir];
    this.stderr = [];
    const child = this.spawnFn(this.cmd.command, args, {
      cwd: this.cmd.cwd,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });
    this.child = child;

    child.stderr?.setEncoding("utf8");
    createInterface({ input: child.stderr! }).on("line", (line) => {
      this.stderr.push(line);
      if (this.stderr.length > STDERR_LINES) this.stderr.shift();
    });

    return new Promise<EngineConnection>((resolvePromise, reject) => {
      let ready = false;
      const timer = setTimeout(() => {
        child.kill();
        reject(new Error(`Engine did not start within ${this.startTimeoutMs / 1000}s.`));
      }, this.startTimeoutMs);

      createInterface({ input: child.stdout! }).on("line", (line) => {
        const port = parseReadyLine(line);
        if (port === null || ready) return;
        ready = true;
        clearTimeout(timer);
        this.connection = { port, token };
        this.setState({ phase: "ready" });
        resolvePromise(this.connection);
      });

      child.on("error", (err: NodeJS.ErrnoException) => {
        clearTimeout(timer);
        const hint = err.code === "ENOENT" ? "Python 3.12+ was not found. Install it and restart." : "";
        reject(new Error(`Could not start engine: ${err.message}. ${hint}`.trim()));
      });

      child.on("exit", (code, signal) => {
        if (child !== this.child && !ready) return;
        clearTimeout(timer);
        if (!ready) {
          // Let the stderr reader flush before reporting.
          setImmediate(() =>
            reject(new Error(`Engine exited (code ${code ?? signal}) before it was ready.\n${this.stderrTail()}`)),
          );
          return;
        }
        if (this.stopping || child !== this.child) return;
        this.onUnexpectedExit(code ?? signal);
      });
    });
  }

  private onUnexpectedExit(code: number | string | null): void {
    this.connection = null;
    if (this.restarts >= MAX_RESTARTS) {
      this.fail(`Engine stopped unexpectedly (code ${code}).\n${this.stderrTail()}`);
      return;
    }
    this.restarts += 1;
    this.setState({ phase: "restarting", message: `Engine stopped (code ${code}). Restarting…` });
    this.launch().catch((err: Error) => this.fail(err.message));
  }
}
