import { describe, expect, it } from "vitest";
import { resolveClipPath } from "../src/main/clipPath";

describe("resolveClipPath", () => {
  it("maps clip URLs into the clips folder", () => {
    expect(resolveClipPath("/data/clips", "clip://media/20261101-183000-r3-death.mp4")).toBe(
      "/data/clips/20261101-183000-r3-death.mp4",
    );
  });

  it("rejects path traversal and other files", () => {
    for (const url of [
      "clip://media/..%2F..%2Fsiegesense.db",
      "clip://media/notes.txt",
      "clip://media/",
      "clip://other/x.mp4",
    ]) {
      expect(resolveClipPath("/data/clips", url)).toBeNull();
    }
  });

  it("dot segments are normalised and stay inside the clips folder", () => {
    expect(resolveClipPath("/data/clips", "clip://media/../secrets.mp4")).toBe("/data/clips/secrets.mp4");
  });
});
