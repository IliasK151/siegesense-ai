// @vitest-environment jsdom
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CalibrationState } from "@shared/protocol";
import { Root } from "@/App";
import { CalibrationPanel } from "@/components/calibration/CalibrationPanel";
import { EngineError } from "@/lib/engineClient";
import { EngineProvider } from "@/lib/engineContext";
import { cmPer360, estimatedCountsPer360 } from "@/lib/aim";
import { useNav } from "@/store/nav";
import { FakeEngine, profileFixture } from "./helpers/fakeEngine";

const user = userEvent.setup();
const armed: CalibrationState = {
  phase: "armed",
  runs: [],
  current_counts: 0,
  target_runs: 3,
  result: null,
  spread: null,
  warning: null,
};

function setup(onResult = vi.fn(), dpi?: number) {
  const engine = new FakeEngine();
  engine.handlers.start_calibration = () => armed;
  engine.handlers.cancel_calibration = () => ({ ...armed, phase: "cancelled" });
  render(
    <EngineProvider client={engine}>
      <CalibrationPanel onResult={onResult} dpi={dpi} />
    </EngineProvider>,
  );
  return { engine, onResult };
}

beforeEach(() => useNav.setState({ page: "home" }));

describe("CalibrationPanel", () => {
  it("starts calibration and shows live counts", async () => {
    const { engine } = setup();
    await user.click(screen.getByRole("button", { name: "Start calibration" }));
    expect(engine.calls.map((c) => c.type)).toContain("start_calibration");
    expect(await screen.findByText("Press F8 in Siege to begin this run.")).toBeInTheDocument();
    act(() => engine.emit("calibration", { ...armed, phase: "measuring", current_counts: 12045 }));
    expect(screen.getByTestId("live-counts")).toHaveTextContent("12,045");
    act(() => engine.emit("calibration", { ...armed, runs: [31416] }));
    expect(screen.getByText("Run 2 of 3")).toBeInTheDocument();
    expect(screen.getByText("31,416")).toBeInTheDocument();
  });

  it("use result sets counts", async () => {
    const { engine, onResult } = setup(vi.fn(), 800);
    await user.click(screen.getByRole("button", { name: "Start calibration" }));
    act(() =>
      engine.emit("calibration", { ...armed, phase: "done", runs: [31400, 31600, 31500], result: 31500, spread: 0.0063 }),
    );
    expect(screen.getByText(/31,500 counts per 360°/)).toBeInTheDocument();
    expect(screen.getByText(/100\.0 cm\/360/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use this result" }));
    expect(onResult).toHaveBeenCalledWith(31500);
  });

  it("shows warning", async () => {
    const { engine } = setup();
    await user.click(screen.getByRole("button", { name: "Start calibration" }));
    act(() => engine.emit("calibration", { ...armed, warning: "That was too small — turn one full circle, then press F8." }));
    expect(screen.getByText(/That was too small/)).toBeInTheDocument();
  });

  it("cancel sends cancel_calibration", async () => {
    const { engine } = setup();
    await user.click(screen.getByRole("button", { name: "Start calibration" }));
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(engine.calls.map((c) => c.type)).toContain("cancel_calibration");
    expect(screen.getByRole("button", { name: "Start calibration" })).toBeInTheDocument();
  });

  it("shows start error", async () => {
    const { engine } = setup();
    engine.handlers.start_calibration = () => {
      throw new EngineError("input_unavailable", "Input tracking works on Windows only");
    };
    await user.click(screen.getByRole("button", { name: "Start calibration" }));
    expect(await screen.findByText("Input tracking works on Windows only")).toBeInTheDocument();
  });
});

describe("aim helpers", () => {
  it("estimates counts and cm per 360", () => {
    const p = { ...profileFixture(), yaw_sensitivity: 10, mouse_multiplier_unit: 0.02, dpi: 800 };
    expect(estimatedCountsPer360(p)).toBeCloseTo(360 / 0.0572957795, 0);
    expect(cmPer360(p)).toBeCloseTo(19.95, 1);
    expect(cmPer360({ ...p, counts_per_360: 36000 })).toBeCloseTo(114.3, 1);
  });
});

describe("calibration in the app", () => {
  it("wizard can skip calibration", async () => {
    const engine = new FakeEngine({ profile: profileFixture() });
    render(<Root client={engine} />);
    await user.click(await screen.findByRole("button", { name: "Edit setup" }));
    await user.click(await screen.findByRole("button", { name: "Get started" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByRole("button", { name: "Skip for now" }));
    expect(await screen.findByRole("heading", { name: "Display" })).toBeInTheDocument();
  });

  it("settings saves calibration", async () => {
    const engine = new FakeEngine({ profile: profileFixture() });
    engine.handlers.start_calibration = () => armed;
    render(<Root client={engine} />);
    await user.click(await screen.findByRole("button", { name: "Settings" }));
    expect(await screen.findByText(/Not calibrated — using estimate/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Calibrate" }));
    await user.click(screen.getByRole("button", { name: "Start calibration" }));
    act(() => engine.emit("calibration", { ...armed, phase: "done", runs: [31500, 31500, 31500], result: 31500, spread: 0 }));
    await user.click(screen.getByRole("button", { name: "Use this result" }));
    const saved = engine.calls.find((c) => c.type === "save_profile")?.payload.profile as { counts_per_360: number };
    expect(saved.counts_per_360).toBe(31500);
    expect(await screen.findByText(/31,500 counts/)).toBeInTheDocument();
  });
});
