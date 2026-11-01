// @vitest-environment jsdom
import { DEFAULT_HUD_REGIONS, type HudCheckResult } from "@shared/protocol";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Root } from "@/App";
import { HudCheck } from "@/components/hud/HudCheck";
import { EngineProvider } from "@/lib/engineContext";
import { useNav } from "@/store/nav";
import { FakeEngine, profileFixture } from "./helpers/fakeEngine";

const user = userEvent.setup();
const check = (): HudCheckResult =>
  JSON.parse(readFileSync(resolve(__dirname, "../../protocol/fixtures/hud_check.json"), "utf8")).payload.data;

function setup(onSave = vi.fn()) {
  const engine = new FakeEngine();
  engine.handlers.hud_check = () => check();
  render(
    <EngineProvider client={engine}>
      <HudCheck regions={DEFAULT_HUD_REGIONS} side="left" inGameName="Ash.Main" onSave={onSave} />
    </EngineProvider>,
  );
  return { engine, onSave };
}

function mockStage() {
  const stage = screen.getByTestId("hud-stage");
  stage.getBoundingClientRect = () =>
    ({ left: 0, top: 0, width: 1000, height: 500, right: 1000, bottom: 500, x: 0, y: 0, toJSON() {} }) as DOMRect;
  return stage;
}

beforeEach(() => useNav.setState({ page: "home" }));

describe("HudCheck", () => {
  it("hud check shows readings", async () => {
    const { engine } = setup();
    await user.click(screen.getByRole("button", { name: "Take screenshot" }));
    const panel = await screen.findByTestId("hud-readings");
    expect(within(panel).getByText("2:45")).toBeInTheDocument();
    expect(within(panel).getByText(/Ash.Main → Thermite_1/)).toBeInTheDocument();
    expect(screen.getByAltText("Screenshot of your game")).toBeInTheDocument();
    expect(engine.calls.find((c) => c.type === "hud_check")?.payload).toMatchObject({
      regions: DEFAULT_HUD_REGIONS,
      my_score_side: "left",
      in_game_name: "Ash.Main",
    });
  });

  it("drag moves box", async () => {
    const { onSave } = setup();
    await user.click(screen.getByRole("button", { name: "Take screenshot" }));
    await screen.findByTestId("hud-readings");
    mockStage();
    const box = screen.getByTestId("box-timer");
    fireEvent.pointerDown(box, { clientX: 500, clientY: 20, pointerId: 1 });
    fireEvent.pointerMove(box, { clientX: 600, clientY: 70, pointerId: 1 });
    fireEvent.pointerUp(box, { clientX: 600, clientY: 70, pointerId: 1 });
    await user.click(screen.getByRole("button", { name: "Save HUD layout" }));
    const [regions] = onSave.mock.calls[0]!;
    expect(regions.timer.x).toBeCloseTo(0.57, 2);
    expect(regions.timer.y).toBeCloseTo(0.115, 2);
    expect(regions.timer.w).toBeCloseTo(0.06, 3);
  });

  it("resize handle changes size", async () => {
    const { onSave } = setup();
    await user.click(screen.getByRole("button", { name: "Take screenshot" }));
    await screen.findByTestId("hud-readings");
    mockStage();
    const handle = screen.getByTestId("resize-health");
    fireEvent.pointerDown(handle, { clientX: 90, clientY: 475, pointerId: 1 });
    fireEvent.pointerMove(handle, { clientX: 140, clientY: 475, pointerId: 1 });
    fireEvent.pointerUp(handle, { pointerId: 1 });
    await user.click(screen.getByRole("button", { name: "Save HUD layout" }));
    expect(onSave.mock.calls[0]![0].health.w).toBeCloseTo(0.12, 2);
  });

  it("reset restores defaults", async () => {
    const { onSave } = setup();
    await user.click(screen.getByRole("button", { name: "Take screenshot" }));
    await screen.findByTestId("hud-readings");
    mockStage();
    const box = screen.getByTestId("box-timer");
    fireEvent.pointerDown(box, { clientX: 500, clientY: 20, pointerId: 1 });
    fireEvent.pointerMove(box, { clientX: 700, clientY: 20, pointerId: 1 });
    fireEvent.pointerUp(box, { pointerId: 1 });
    await user.click(screen.getByRole("button", { name: "Reset to defaults" }));
    await user.click(screen.getByRole("button", { name: "Save HUD layout" }));
    expect(onSave.mock.calls[0]![0]).toEqual(DEFAULT_HUD_REGIONS);
  });

  it("stage keeps the screenshot's aspect ratio (ultrawide)", async () => {
    const { engine } = setup();
    engine.handlers.hud_check = () => ({ ...check(), width: 960, height: 405 });
    await user.click(screen.getByRole("button", { name: "Take screenshot" }));
    await screen.findByTestId("hud-readings");
    expect(screen.getByTestId("hud-stage").style.aspectRatio).toBe("960 / 405");
    expect(screen.getByAltText("Screenshot of your game").className).not.toContain("object-cover");
  });

  it("score side toggle", async () => {
    const { onSave } = setup();
    await user.click(screen.getByRole("radio", { name: "Right" }));
    await user.click(screen.getByRole("button", { name: "Save HUD layout" }));
    expect(onSave.mock.calls[0]![1]).toBe("right");
  });
});

describe("HUD check in the app", () => {
  it("save updates profile", async () => {
    const engine = new FakeEngine({ profile: profileFixture() });
    engine.handlers.hud_check = () => check();
    render(<Root client={engine} />);
    await user.click(await screen.findByRole("button", { name: "Settings" }));
    await user.click(await screen.findByRole("button", { name: "Open HUD check" }));
    await user.click(screen.getByRole("radio", { name: "Right" }));
    await user.click(screen.getByRole("button", { name: "Save HUD layout" }));
    const saved = engine.calls.find((c) => c.type === "save_profile")?.payload.profile as { my_score_side: string };
    expect(saved.my_score_side).toBe("right");
  });

  it("wizard can skip hud step", async () => {
    const engine = new FakeEngine({ profile: profileFixture() });
    render(<Root client={engine} />);
    await user.click(await screen.findByRole("button", { name: "Edit setup" }));
    await user.click(await screen.findByRole("button", { name: "Get started" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByRole("button", { name: "Skip for now" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByRole("heading", { name: "Check your HUD" });
    await user.click(screen.getByRole("button", { name: "Skip HUD check" }));
    expect(await screen.findByRole("button", { name: "Save profile" })).toBeInTheDocument();
  });
});
