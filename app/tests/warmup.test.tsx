// @vitest-environment jsdom
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Root } from "@/App";
import { EngineError } from "@/lib/engineClient";
import { useNav } from "@/store/nav";
import { useWarmup } from "@/store/warmup";
import { FakeEngine, flickFixture, metricsFixture, profileFixture, summaryFixture } from "./helpers/fakeEngine";

const user = userEvent.setup();

function setup(profile = profileFixture()) {
  const engine = new FakeEngine({ profile });
  engine.handlers.start_warmup = () => ({ conversion: profile.counts_per_360 ? "calibrated" : "estimated" });
  engine.handlers.stop_warmup = () => summaryFixture();
  engine.handlers.get_warmup_history = () => ({ history: summaryFixture().history.slice(0, 1) });
  render(<Root client={engine} />);
  return engine;
}

async function openWarmup() {
  await user.click(await screen.findByRole("button", { name: "Warm-up" }));
  await screen.findByRole("heading", { name: "Warm-up" });
}

async function start() {
  await openWarmup();
  await user.click(screen.getByRole("button", { name: "Start warm-up" }));
  await screen.findByText("LIVE");
}

beforeEach(() => {
  useNav.setState({ page: "home" });
  useWarmup.getState().reset();
});
afterEach(() => {
  delete window.siegesense;
});

describe("Warm-up page", () => {
  it("start shows live tiles", async () => {
    const engine = setup();
    await start();
    expect(engine.calls.map((c) => c.type)).toContain("start_warmup");
    expect(screen.getByTestId("tile-score")).toHaveTextContent("—");
    expect(screen.getByTestId("tile-flicks")).toHaveTextContent("0");
  });

  it("metrics push updates tiles", async () => {
    const engine = setup();
    await start();
    act(() => engine.emit("metrics", metricsFixture()));
    expect(screen.getByTestId("tile-score")).toHaveTextContent("58");
    expect(screen.getByTestId("tile-flicks")).toHaveTextContent("12");
    expect(screen.getByTestId("tile-overshoot")).toHaveTextContent("42%");
  });

  it("flick push adds tagged row and chart", async () => {
    const engine = setup();
    await start();
    act(() => engine.emit("flick", flickFixture()));
    const list = screen.getByTestId("flick-list");
    expect(within(list).getByText("Overshoot")).toBeInTheDocument();
    expect(screen.getByTestId("flick-chart")).toBeInTheDocument();
  });

  it("stop shows summary with drill", async () => {
    const engine = setup();
    await start();
    await user.click(screen.getByRole("button", { name: "Stop" }));
    expect(engine.calls.map((c) => c.type)).toContain("stop_warmup");
    expect(await screen.findByText("Overshooting your flicks")).toBeInTheDocument();
    expect(screen.getByTestId("summary-score")).toHaveTextContent("58");
    await user.click(screen.getByRole("button", { name: "New warm-up" }));
    expect(screen.getByRole("button", { name: "Start warm-up" })).toBeInTheDocument();
  });

  it("shows estimated badge", async () => {
    setup();
    await openWarmup();
    expect(screen.getByText("Estimated — calibrate in Settings")).toBeInTheDocument();
  });

  it("shows calibrated badge", async () => {
    setup({ ...profileFixture(), counts_per_360: 31500 });
    await openWarmup();
    expect(screen.getByText("Calibrated")).toBeInTheDocument();
  });

  it("start error shown", async () => {
    const engine = setup();
    engine.handlers.start_warmup = () => {
      throw new EngineError("input_unavailable", "Input tracking works on Windows only");
    };
    await openWarmup();
    await user.click(screen.getByRole("button", { name: "Start warm-up" }));
    expect(await screen.findByText("Input tracking works on Windows only")).toBeInTheDocument();
  });

  it("toggles overlay", async () => {
    const setOverlayVisible = vi.fn();
    window.siegesense = { setOverlayVisible } as never;
    setup();
    await start();
    expect(setOverlayVisible).toHaveBeenLastCalledWith(true);
    await user.click(screen.getByRole("button", { name: "Stop" }));
    await screen.findByTestId("summary-score");
    expect(setOverlayVisible).toHaveBeenLastCalledWith(false);
  });

  it("home start warm-up opens the page", async () => {
    setup();
    await user.click(await screen.findByRole("button", { name: "Start Warm-up" }));
    expect(await screen.findByRole("heading", { name: "Warm-up" })).toBeInTheDocument();
  });
});
