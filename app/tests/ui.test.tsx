// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { StatusLight } from "@/components/ui/StatusLight";

describe("ui components", () => {
  it("StatusLight shows fix in tooltip", async () => {
    render(
      <StatusLight
        lightKey="game"
        light={{ state: "warn", label: "Siege not running", detail: "Not detected.", fix: "Launch Rainbow Six Siege" }}
      />,
    );
    const light = screen.getByLabelText("Siege not running: Not detected.");
    await userEvent.hover(light);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Launch Rainbow Six Siege");
  });

  it("Field shows error with role alert", () => {
    render(<Field label="DPI" error="Required" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Required");
    expect(screen.getByLabelText("DPI")).toHaveAttribute("aria-invalid", "true");
  });

  it("Button loading disables", () => {
    render(<Button loading>Save</Button>);
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });
});
