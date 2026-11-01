import { join } from "node:path";

const CLIP_NAME = /^[\w.-]+\.mp4$/;

/** Maps `clip://media/<name>.mp4` to a file inside the clips folder, or null if unsafe. */
export function resolveClipPath(clipsDir: string, url: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== "clip:" || parsed.hostname !== "media") return null;
  let name: string;
  try {
    name = decodeURIComponent(parsed.pathname.replace(/^\/+/, ""));
  } catch {
    return null;
  }
  if (!CLIP_NAME.test(name) || name.includes("..")) return null;
  return join(clipsDir, name);
}
