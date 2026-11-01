import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import { describe, expect, it } from "vitest";
import {
  EngineSupervisor,
  type EngineState,
  parseReadyLine,
  resolveEngineCommand,
} from "../src/main/engineProcess";

class FakeChild extends EventEmitter {
  stdout = new PassThrough();
  stderr = new PassThrough();
  stdin = new PassThrough();
  killed = false;
  kill() {
    this.killed = true;
    queueMicrotask(() => this.emit("exit", null, "SIGTERM"));
    return true;
  }
  ready(port: number) {
    this.stdout.write(`READY ${port}\n`);
  }
  crash(code = 1) {
    this.emit("exit", code, null);
  }
}

function fakeSpawn() {
  const children: FakeChild[] = [];
  const calls: { command: string; args: string[] }[] = [];
  const spawnFn = ((command: string, args: string[]) => {
    const child = new FakeChild();
    children.push(child);
    calls.push({ command, args });
    return child;
  }) as never;
  return { spawnFn, children, calls };
}

const cmd = { command: "python3", args: ["-m", "siegesense_engine"] };
const tick = () => new Promise((r) => setTimeout(r, 5));

describe("engineProcess", () => {
  it("parses ready line", () => {
    expect(parseReadyLine("READY 51234\n")).toBe(51234);
    expect(parseReadyLine("READY 51234\r\n")).toBe(51234);
    expect(parseReadyLine("hi")).toBeNull();
  });

  it("resolves dev and packaged commands", () => {
    const dev = resolveEngineCommand({ isPackaged: false, resourcesPath: "/r", appRoot: "/repo/app" }, "linux");
    expect(dev).toEqual({ command: "python3", args: ["-m", "siegesense_engine"], cwd: "/repo/engine/src" });
    const win = resolveEngineCommand({ isPackaged: false, resourcesPath: "/r", appRoot: "/repo/app" }, "win32");
    expect(win.command).toBe("py");
    expect(win.args).toEqual(["-3", "-m", "siegesense_engine"]);
    const packed = resolveEngineCommand({ isPackaged: true, resourcesPath: "/r", appRoot: "/a" }, "win32");
    expect(packed.command.replaceAll("\\", "/")).toBe("/r/engine/siegesense-engine.exe");
  });

  it("resolves connection on ready and passes token and data dir args", async () => {
    const { spawnFn, children, calls } = fakeSpawn();
    const sup = new EngineSupervisor(cmd, { dataDir: "/data", spawnFn });
    const started = sup.start();
    children[0]!.ready(4000);
    const conn = await started;
    expect(conn.port).toBe(4000);
    expect(conn.token).toMatch(/^[0-9a-f]{48}$/);
    const args = calls[0]!.args;
    expect(args.slice(0, 2)).toEqual(["-m", "siegesense_engine"]);
    expect(args[args.indexOf("--token") + 1]).toBe(conn.token);
    expect(args[args.indexOf("--data-dir") + 1]).toBe("/data");
    expect(sup.connection).toEqual(conn);
  });

  it("times out without ready line", async () => {
    const { spawnFn, children } = fakeSpawn();
    const states: EngineState[] = [];
    const sup = new EngineSupervisor(cmd, { dataDir: "/d", spawnFn, startTimeoutMs: 30 });
    sup.on("state", (s: EngineState) => states.push(s));
    await expect(sup.start()).rejects.toThrow(/did not start/);
    expect(states.at(-1)?.phase).toBe("failed");
    expect(children[0]!.killed).toBe(true);
  });

  it("fails with stderr when engine exits before ready", async () => {
    const { spawnFn, children } = fakeSpawn();
    const sup = new EngineSupervisor(cmd, { dataDir: "/d", spawnFn });
    const started = sup.start();
    children[0]!.stderr.write("ModuleNotFoundError: No module named 'websockets'\n");
    await tick();
    children[0]!.crash(1);
    await expect(started).rejects.toThrow(/websockets/);
  });

  it("fails clearly when python cannot be spawned", async () => {
    const { spawnFn, children } = fakeSpawn();
    const sup = new EngineSupervisor(cmd, { dataDir: "/d", spawnFn });
    const started = sup.start();
    children[0]!.emit("error", Object.assign(new Error("spawn python3 ENOENT"), { code: "ENOENT" }));
    await expect(started).rejects.toThrow(/Python/);
  });

  it("restarts once then gives up", async () => {
    const { spawnFn, children } = fakeSpawn();
    const states: EngineState[] = [];
    const sup = new EngineSupervisor(cmd, { dataDir: "/d", spawnFn });
    sup.on("state", (s: EngineState) => states.push(s));
    const started = sup.start();
    children[0]!.ready(4000);
    await started;
    children[0]!.crash();
    await tick();
    expect(children).toHaveLength(2);
    expect(states.map((s) => s.phase)).toContain("restarting");
    children[1]!.ready(4001);
    await tick();
    expect(sup.connection?.port).toBe(4001);
    expect(states.at(-1)?.phase).toBe("ready");
    children[1]!.stderr.write("boom\n");
    await tick();
    children[1]!.crash();
    await tick();
    expect(children).toHaveLength(2);
    expect(states.at(-1)).toMatchObject({ phase: "failed" });
    expect(states.at(-1)?.message).toContain("boom");
    expect(sup.connection).toBeNull();
  });

  it("stop does not trigger a restart", async () => {
    const { spawnFn, children } = fakeSpawn();
    const sup = new EngineSupervisor(cmd, { dataDir: "/d", spawnFn });
    const started = sup.start();
    children[0]!.ready(4000);
    await started;
    sup.stop();
    await tick();
    expect(children).toHaveLength(1);
  });
});
