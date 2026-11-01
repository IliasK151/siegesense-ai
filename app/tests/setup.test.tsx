// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_HUD_REGIONS } from "@shared/protocol";
import { Root } from "@/App";
import { EngineError } from "@/lib/engineClient";
import { useNav } from "@/store/nav";
import { FakeEngine, profileFixture } from "./helpers/fakeEngine";

const IMPORTED = {
  values: {
    yaw_sensitivity: 12,
    pitch_sensitivity: 11,
    ads_sensitivity: { "1x": 55, "2.5x": 60, "3x": 65, "4x": 70, "5x": 75, "12x": 80 },
    resolution_width: 2560,
    resolution_height: 1440,
    window_mode: "borderless",
  },
  missing: ["fov"],
  source: "/docs/My Games/Rainbow Six - Siege/abc/GameSettings.ini",
};

function firstRun(overrides: Partial<typeof IMPORTED> = {}) {
  const engine = new FakeEngine({ profile: null });
  engine.handlers.find_game_settings = () => ({ files: [{ path: IMPORTED.source, modified: 1_760_000_000 }] });
  engine.handlers.import_game_settings = () => ({ ...IMPORTED, ...overrides });
  render(<Root client={engine} />);
  return engine;
}

const next = () => screen.getByRole("button", { name: "Next" });
const user = userEvent.setup();

async function toSensitivity(name = "Ash.Main") {
  await user.click(await screen.findByRole("button", { name: "Get started" }));
  await user.type(screen.getByLabelText("In-game name"), name);
  await user.click(next());
  await screen.findByRole("heading", { name: "Sensitivity" });
}

async function skipCalibration() {
  await user.click(next());
  await user.click(await screen.findByRole("button", { name: "Skip for now" }));
}

beforeEach(() => useNav.setState({ page: "home" }));
afterEach(() => {
  delete window.siegesense;
});

describe("setup wizard", () => {
  it("blocks next on invalid name", async () => {
    firstRun();
    await user.click(await screen.findByRole("button", { name: "Get started" }));
    await user.type(screen.getByLabelText("In-game name"), "ab");
    expect(next()).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("3–15 characters: letters, numbers, . _ -");
  });

  it("imports found settings", async () => {
    const engine = firstRun();
    await toSensitivity();
    expect(await screen.findByText("Found your Siege settings")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Import" }));
    expect(screen.getByLabelText("Horizontal sensitivity")).toHaveValue(12);
    expect(screen.getAllByText("Imported").length).toBeGreaterThan(0);
    expect(engine.calls.find((c) => c.type === "import_game_settings")?.payload).toEqual({ path: IMPORTED.source });
    await user.type(screen.getByLabelText("Mouse DPI"), "800");
    await skipCalibration();
    await screen.findByRole("heading", { name: "Display" });
    const fov = screen.getByLabelText("Field of view").closest("div")!.parentElement!;
    expect(within(fov).getByText("Not found — enter manually")).toBeInTheDocument();
  });

  it("browse uses pickFile", async () => {
    const pickFile = vi.fn(async () => "/picked/GameSettings.ini");
    window.siegesense = { pickFile } as never;
    const engine = firstRun();
    await toSensitivity();
    await user.click(screen.getByRole("button", { name: "Browse…" }));
    expect(pickFile).toHaveBeenCalledWith([{ name: "Siege settings", extensions: ["ini"] }]);
    expect(engine.calls.find((c) => c.type === "import_game_settings")?.payload).toEqual({
      path: "/picked/GameSettings.ini",
    });
  });

  it("requires dpi", async () => {
    firstRun();
    await toSensitivity();
    await user.click(await screen.findByRole("button", { name: "Import" }));
    expect(next()).toBeDisabled();
    await user.type(screen.getByLabelText("Mouse DPI"), "50");
    expect(next()).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Between 100 and 32000");
    await user.clear(screen.getByLabelText("Mouse DPI"));
    await user.type(screen.getByLabelText("Mouse DPI"), "800");
    expect(next()).toBeEnabled();
    expect(screen.getByTestId("draft-edpi")).toHaveTextContent("9600");
  });

  it("fullscreen shows borderless warning", async () => {
    firstRun({ values: { ...IMPORTED.values, window_mode: "fullscreen" } });
    await toSensitivity();
    await user.click(await screen.findByRole("button", { name: "Import" }));
    await user.type(screen.getByLabelText("Mouse DPI"), "800");
    await skipCalibration();
    expect(await screen.findByText(/Switch Siege to Borderless/)).toBeInTheDocument();
  });

  it("saves profile and goes home", async () => {
    const engine = firstRun();
    await toSensitivity();
    await user.click(await screen.findByRole("button", { name: "Import" }));
    await user.type(screen.getByLabelText("Mouse DPI"), "800");
    await skipCalibration();
    await user.type(screen.getByLabelText("Field of view"), "84");
    await user.click(next());
    await user.click(await screen.findByRole("button", { name: "Save profile" }));
    expect(await screen.findByTestId("status-card")).toBeInTheDocument();
    expect(engine.calls.find((c) => c.type === "save_profile")?.payload).toEqual({
      profile: {
        in_game_name: "Ash.Main",
        dpi: 800,
        yaw_sensitivity: 12,
        pitch_sensitivity: 11,
        mouse_multiplier_unit: 0.02,
        x_factor_aiming: 0.02,
        ads_sensitivity: IMPORTED.values.ads_sensitivity,
        fov: 84,
        resolution_width: 2560,
        resolution_height: 1440,
        hud_scale: 100,
        window_mode: "borderless",
        hud_regions: DEFAULT_HUD_REGIONS,
        my_score_side: "left",
        capture_fps: 30,
      },
    });
  });

  it("shows engine error on save failure", async () => {
    const engine = firstRun();
    engine.handlers.save_profile = () => {
      throw new EngineError("invalid_profile", "dpi too low");
    };
    await toSensitivity();
    await user.click(await screen.findByRole("button", { name: "Import" }));
    await user.type(screen.getByLabelText("Mouse DPI"), "800");
    await skipCalibration();
    await user.type(screen.getByLabelText("Field of view"), "84");
    await user.click(next());
    await user.click(await screen.findByRole("button", { name: "Save profile" }));
    expect(await screen.findByText("dpi too low")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save profile" })).toBeInTheDocument();
  });

  it("prefills from existing profile", async () => {
    render(<Root client={new FakeEngine({ profile: profileFixture() })} />);
    await user.click(await screen.findByRole("button", { name: "Edit setup" }));
    await user.click(await screen.findByRole("button", { name: "Get started" }));
    expect(screen.getByLabelText("In-game name")).toHaveValue("Ash.Main");
    await user.click(next());
    expect(screen.getByLabelText("Mouse DPI")).toHaveValue(800);
  });

  it("drops invalid imported values instead of blocking save", async () => {
    const engine = firstRun({
      values: { ...IMPORTED.values, mouse_multiplier_unit: 5, fov: 120 } as typeof IMPORTED.values,
      missing: [],
    });
    await toSensitivity();
    await user.click(await screen.findByRole("button", { name: "Import" }));
    await user.type(screen.getByLabelText("Mouse DPI"), "800");
    await skipCalibration();
    const fov = screen.getByLabelText("Field of view");
    expect(fov).toHaveValue(null);
    expect(within(fov.closest("div")!.parentElement!).getByText("Not found — enter manually")).toBeInTheDocument();
    await user.type(fov, "84");
    await user.click(next());
    await user.click(await screen.findByRole("button", { name: "Save profile" }));
    expect(await screen.findByTestId("status-card")).toBeInTheDocument();
    const saved = engine.calls.find((c) => c.type === "save_profile")?.payload.profile as Record<string, unknown>;
    expect(saved.mouse_multiplier_unit).toBe(0.02);
    expect(saved.fov).toBe(84);
  });
});

