// @vitest-environment jsdom
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { Root } from "@/App";
import { useNav } from "@/store/nav";
import { FakeEngine, profileFixture } from "./helpers/fakeEngine";

beforeEach(() => useNav.setState({ page: "home" }));

describe("app shell", () => {
  it("redirects to setup when no profile", async () => {
    render(<Root client={new FakeEngine({ profile: null })} />);
    expect(await screen.findByTestId("setup-wizard")).toBeInTheDocument();
  });

  it("home shows six status lights", async () => {
    render(<Root client={new FakeEngine()} />);
    const card = await screen.findByTestId("status-card");
    expect(within(card).getAllByTestId("status-light")).toHaveLength(6);
  });

  it("shows reconnecting banner", async () => {
    const engine = new FakeEngine();
    render(<Root client={engine} />);
    await screen.findByTestId("status-card");
    act(() => engine.emitState("reconnecting"));
    expect(screen.getByText(/Reconnecting to engine/)).toBeInTheDocument();
    act(() => engine.emitState("open"));
    expect(screen.queryByText(/Reconnecting to engine/)).not.toBeInTheDocument();
  });

  it("shows failed engine banner", async () => {
    let push: (s: { phase: "failed"; message: string }) => void = () => {};
    render(<Root client={new FakeEngine()} onEngineState={(cb) => ((push = cb), () => {})} />);
    await screen.findByTestId("status-card");
    act(() => push({ phase: "failed", message: "Python 3.12+ was not found." }));
    expect(screen.getByText("Engine stopped")).toBeInTheDocument();
    expect(screen.getByText(/Python 3.12\+ was not found/)).toBeInTheDocument();
  });

  it("sidebar navigates to review", async () => {
    render(<Root client={new FakeEngine()} />);
    await screen.findByTestId("status-card");
    await userEvent.click(screen.getByRole("button", { name: "Review" }));
    expect(await screen.findByRole("heading", { name: "Session Review" })).toBeInTheDocument();
  });

  it("eDPI computed", async () => {
    render(<Root client={new FakeEngine({ profile: { ...profileFixture(), dpi: 800, yaw_sensitivity: 10 } })} />);
    expect(await screen.findByTestId("edpi")).toHaveTextContent("8000");
  });

  it("live status push updates lights", async () => {
    const engine = new FakeEngine();
    render(<Root client={engine} />);
    await screen.findByTestId("status-card");
    const status = await engine.request<import("@shared/protocol").StatusPayload>("get_status");
    act(() =>
      engine.emitStatus({
        lights: { ...status.lights, game: { state: "ok", label: "Siege running", detail: "Focused." } },
      }),
    );
    expect(screen.getAllByLabelText("Siege running: Focused.").length).toBeGreaterThan(0);
  });
});
