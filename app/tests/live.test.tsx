// @vitest-environment jsdom
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { Root } from "@/App";
import { EngineError } from "@/lib/engineClient";
import { useLive } from "@/store/live";
import { useNav } from "@/store/nav";
import { FakeEngine } from "./helpers/fakeEngine";

const fx = (name: string) =>
  JSON.parse(readFileSync(resolve(__dirname, "../../protocol/fixtures", name), "utf8")).payload;
const user = userEvent.setup();

function setup() {
  const engine = new FakeEngine();
  engine.handlers.start_live = () => ({ started_at: "2026-11-01T18:30:00+00:00" });
  engine.handlers.stop_live = () => fx("match_summary.json").data;
  render(<Root client={engine} />);
  return engine;
}

async function openLive() {
  await user.click(await screen.findByRole("button", { name: "Live" }));
  await screen.findByTestId("live-checklist");
}

async function startLive() {
  await openLive();
  await user.click(screen.getByRole("button", { name: "Start Live Mode" }));
  await screen.findByText("LIVE", { exact: true });
}

beforeEach(() => {
  useNav.setState({ page: "home" });
  useLive.getState().reset();
});

describe("Live page", () => {
  it("start live shows checklist and live", async () => {
    const engine = setup();
    await openLive();
    await user.click(screen.getByRole("button", { name: "Start Live Mode" }));
    expect(await screen.findByText("LIVE", { exact: true })).toBeInTheDocument();
    expect(engine.calls.map((c) => c.type)).toContain("start_live");
  });

  it("round summary updates strip", async () => {
    const engine = setup();
    await startLive();
    act(() => engine.emit("round_summary", fx("round_summary.json")));
    const chip = within(screen.getByTestId("round-strip")).getByTestId("round-3");
    expect(chip).toHaveTextContent("L");
    expect(chip).toHaveAttribute("aria-label", expect.stringContaining("died"));
  });

  it("death event shows clip card", async () => {
    const engine = setup();
    await startLive();
    act(() => engine.emit("live_event", fx("live_event.json")));
    const card = screen.getByTestId("death-card");
    expect(within(card).getByText(/Killed by Bandit.X/)).toBeInTheDocument();
    expect(card.querySelector("video")).toHaveAttribute("src", "clip://media/20261101-183000-r3-death.mp4");
    expect(within(card).getByText(/41.2 s alive/)).toBeInTheDocument();
  });

  it("low confidence dimmed", async () => {
    const engine = setup();
    await startLive();
    act(() => engine.emit("live_event", { ...fx("live_event.json"), confidence: "low", clip: null }));
    const feed = screen.getByTestId("event-feed");
    expect(within(feed).getByText(/unsure/)).toBeInTheDocument();
  });

  it("stop shows match summary", async () => {
    const engine = setup();
    await startLive();
    await user.click(screen.getByRole("button", { name: "Stop" }));
    expect(engine.calls.map((c) => c.type)).toContain("stop_live");
    const summary = await screen.findByTestId("match-summary");
    expect(within(summary).getByTestId("stat-rounds")).toHaveTextContent("0–1");
    expect(within(summary).getByTestId("stat-deaths")).toHaveTextContent("1");
  });

  it("start error shown", async () => {
    const engine = setup();
    engine.handlers.start_live = () => {
      throw new EngineError("capture_unavailable", "Screen capture works on Windows only");
    };
    await openLive();
    await user.click(screen.getByRole("button", { name: "Start Live Mode" }));
    expect(await screen.findByText("Screen capture works on Windows only")).toBeInTheDocument();
  });

  it("home start live mode opens the page", async () => {
    setup();
    await user.click(await screen.findByRole("button", { name: "Start Live Mode" }));
    expect(await screen.findByTestId("live-checklist")).toBeInTheDocument();
  });
});
