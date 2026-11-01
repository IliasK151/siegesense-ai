import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import WebSocket, { WebSocketServer } from "ws";
import { EngineClient, EngineError, type ConnState } from "../src/renderer/src/lib/engineClient";

type Msg = { type: string; id?: string; ts: number; payload: Record<string, unknown> };
let server: WebSocketServer;
let port: number;
let received: Msg[];
let reply: (msg: Msg, ws: WebSocket) => void;

const respond = (ws: WebSocket, id: string | undefined, payload: unknown) =>
  ws.send(JSON.stringify({ type: "response", id, ts: 0, payload }));

beforeEach(async () => {
  received = [];
  reply = (msg, ws) => respond(ws, msg.id, { ok: true, data: { echo: msg.type } });
  server = new WebSocketServer({ port: 0, host: "127.0.0.1" });
  await new Promise<void>((r) => server.once("listening", () => r()));
  port = (server.address() as { port: number }).port;
  server.on("connection", (ws) => {
    ws.on("message", (raw) => {
      const msg = JSON.parse(String(raw)) as Msg;
      received.push(msg);
      if (msg.type === "hello") respond(ws, msg.id, { ok: true, data: { engine_version: "t" } });
      else reply(msg, ws);
    });
  });
});

afterEach(async () => {
  for (const c of server.clients) c.terminate();
  await new Promise((r) => server.close(r));
});

const client = (opts = {}) =>
  new EngineClient(async () => ({ port, token: "tok" }), {
    WebSocketImpl: WebSocket as unknown as typeof globalThis.WebSocket,
    backoffMs: [10, 20],
    ...opts,
  });

const until = async (cond: () => boolean, ms = 1000) => {
  const start = Date.now();
  while (!cond()) {
    if (Date.now() - start > ms) throw new Error("timeout waiting for condition");
    await new Promise((r) => setTimeout(r, 5));
  }
};

describe("EngineClient", () => {
  it("sends hello first", async () => {
    const c = client();
    await c.connect();
    expect(received[0]).toMatchObject({ type: "hello", payload: { token: "tok" } });
    c.close();
  });

  it("request resolves data", async () => {
    const c = client();
    await c.connect();
    await expect(c.request("get_profile")).resolves.toEqual({ echo: "get_profile" });
    c.close();
  });

  it("request rejects EngineError on ok false", async () => {
    reply = (msg, ws) => respond(ws, msg.id, { ok: false, error: { code: "invalid_profile", message: "dpi" } });
    const c = client();
    await c.connect();
    const err = await c.request("save_profile", {}).catch((e) => e);
    expect(err).toBeInstanceOf(EngineError);
    expect(err).toMatchObject({ code: "invalid_profile", message: "dpi" });
    c.close();
  });

  it("request times out", async () => {
    reply = () => {};
    const c = client({ requestTimeoutMs: 30 });
    await c.connect();
    await expect(c.request("get_status")).rejects.toMatchObject({ code: "timeout" });
    c.close();
  });

  it("delivers status events", async () => {
    const c = client();
    const seen: unknown[] = [];
    c.on("status", (p) => seen.push(p));
    await c.connect();
    const { lights } = JSON.parse(
      readFileSync(resolve(__dirname, "../../protocol/fixtures/status.json"), "utf8"),
    ).payload;
    for (const ws of server.clients) ws.send(JSON.stringify({ type: "status", ts: 1, payload: { lights } }));
    await until(() => seen.length === 1);
    expect(seen[0]).toEqual({ lights });
    c.close();
  });

  it("reconnects after close", async () => {
    const c = client();
    const states: ConnState[] = [];
    c.onState((s) => states.push(s));
    await c.connect();
    for (const ws of server.clients) ws.close();
    await until(() => states.at(-1) === "open" && states.includes("reconnecting"));
    expect(received.filter((m) => m.type === "hello")).toHaveLength(2);
    c.close();
    expect(states.at(-1)).toBe("closed");
  });

  it("rejects pending requests when disconnected", async () => {
    reply = (_msg, ws) => ws.close();
    const c = client();
    await c.connect();
    await expect(c.request("get_status")).rejects.toMatchObject({ code: "disconnected" });
    c.close();
  });
});
