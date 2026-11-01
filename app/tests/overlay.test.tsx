// @vitest-environment jsdom
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OverlayApp } from "@/overlay/OverlayApp";
import { FakeEngine, flickFixture, metricsFixture } from "./helpers/fakeEngine";

describe("warm-up overlay", () => {
  it("overlay shows metrics from push", () => {
    const engine = new FakeEngine();
    render(<OverlayApp client={engine} />);
    expect(screen.getByTestId("overlay-score")).toHaveTextContent("—");
    act(() => engine.emit("metrics", metricsFixture()));
    expect(screen.getByTestId("overlay-score")).toHaveTextContent("58");
    expect(screen.getByTestId("overlay-overshoot")).toHaveTextContent("42%");
    expect(screen.getByTestId("overlay-flicks")).toHaveTextContent("12");
  });

  it("overlay shows last flick tag", () => {
    const engine = new FakeEngine();
    render(<OverlayApp client={engine} />);
    act(() => engine.emit("flick", { ...flickFixture(), id: 7 }));
    expect(screen.getByTestId("overlay-tag")).toHaveTextContent("Overshoot");
    act(() => engine.emit("flick", { ...flickFixture(), id: 8, overshoot: false, corrected: false }));
    expect(screen.getByTestId("overlay-tag")).toHaveTextContent("Clean");
  });
});
