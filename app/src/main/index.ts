import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { app, BrowserWindow, dialog, ipcMain, net, protocol, screen } from "electron";
import { IPC, type EngineConnection, type EngineState, type FileFilter } from "../preload/api";
import { resolveClipPath } from "./clipPath";
import { EngineSupervisor, resolveEngineCommand } from "./engineProcess";

// Death clips are served from the engine's clips folder only (see clipPath.ts).
protocol.registerSchemesAsPrivileged([
  { scheme: "clip", privileges: { standard: true, secure: true, stream: true, supportFetchAPI: true } },
]);

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) app.quit();

let win: BrowserWindow | null = null;
let lastState: EngineState = { phase: "starting" };
const readyWaiters: ((c: EngineConnection) => void)[] = [];

const supervisor = new EngineSupervisor(
  resolveEngineCommand({
    isPackaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
    appRoot: app.getAppPath(),
  }),
  { dataDir: app.getPath("userData") },
);

supervisor.on("state", (s: EngineState) => {
  lastState = s;
  win?.webContents.send(IPC.engineState, s);
  if (s.phase === "ready" && supervisor.connection) {
    for (const resolve of readyWaiters.splice(0)) resolve(supervisor.connection);
  }
});

ipcMain.handle(IPC.engineGet, () =>
  supervisor.connection
    ? supervisor.connection
    : new Promise<EngineConnection>((resolve) => readyWaiters.push(resolve)),
);

ipcMain.handle(IPC.pickFile, async (_e, filters?: FileFilter[]) => {
  const result = await dialog.showOpenDialog(win!, { properties: ["openFile"], filters });
  return result.canceled ? null : (result.filePaths[0] ?? null);
});

// --- Warm-up overlay: small, transparent, click-through, never takes focus from the game.
let overlay: BrowserWindow | null = null;
const OVERLAY_SIZE = { width: 300, height: 140 };
const OVERLAY_MARGIN = 24;

function getOverlay(): BrowserWindow {
  if (overlay && !overlay.isDestroyed()) return overlay;
  const area = screen.getPrimaryDisplay().workArea;
  overlay = new BrowserWindow({
    ...OVERLAY_SIZE,
    x: area.x + area.width - OVERLAY_SIZE.width - OVERLAY_MARGIN,
    y: area.y + OVERLAY_MARGIN,
    show: false,
    transparent: true,
    frame: false,
    resizable: false,
    movable: false,
    skipTaskbar: true,
    focusable: false,
    hasShadow: false,
    alwaysOnTop: true,
    webPreferences: { preload: join(__dirname, "../preload/index.mjs"), sandbox: false },
  });
  overlay.setAlwaysOnTop(true, "screen-saver");
  overlay.setIgnoreMouseEvents(true);
  overlay.setVisibleOnAllWorkspaces(true);
  overlay.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  if (process.env.ELECTRON_RENDERER_URL) void overlay.loadURL(`${process.env.ELECTRON_RENDERER_URL}/overlay.html`);
  else void overlay.loadFile(join(__dirname, "../renderer/overlay.html"));
  return overlay;
}

ipcMain.on(IPC.overlaySet, (_e, visible: boolean) => {
  if (visible) getOverlay().showInactive();
  else if (overlay && !overlay.isDestroyed()) overlay.hide();
});

function createWindow(): void {
  win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    backgroundColor: "#0A0C0F",
    titleBarStyle: "hidden",
    ...(process.platform === "win32"
      ? { titleBarOverlay: { color: "#0A0C0F", symbolColor: "#E7EBF0", height: 40 } }
      : {}),
    webPreferences: { preload: join(__dirname, "../preload/index.mjs"), sandbox: false },
  });
  win.once("ready-to-show", () => win?.show());
  win.on("closed", () => {
    win = null;
    app.quit();
  });
  // Defense in depth: this window holds the engine token, so it never navigates or opens popups.
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (event, url) => {
    const own = process.env.ELECTRON_RENDERER_URL ?? "file://";
    if (!url.startsWith(own)) event.preventDefault();
  });
  win.webContents.on("did-finish-load", () => win?.webContents.send(IPC.engineState, lastState));
  if (process.env.ELECTRON_RENDERER_URL) void win.loadURL(process.env.ELECTRON_RENDERER_URL);
  else void win.loadFile(join(__dirname, "../renderer/index.html"));
}

void app.whenReady().then(() => {
  if (!gotLock) return; // another SiegeSense is already running; it gets focused instead
  const clipsDir = join(app.getPath("userData"), "clips");
  protocol.handle("clip", (request) => {
    const file = resolveClipPath(clipsDir, request.url);
    return file ? net.fetch(pathToFileURL(file).toString()) : new Response("Not found", { status: 404 });
  });
  createWindow();
  supervisor.start().catch(() => {
    /* state "failed" is already forwarded to the renderer */
  });
});

app.on("second-instance", () => {
  if (!win) return;
  if (win.isMinimized()) win.restore();
  win.focus();
});

app.on("window-all-closed", () => app.quit());
app.on("before-quit", () => {
  if (overlay && !overlay.isDestroyed()) overlay.destroy();
});
app.on("before-quit", () => supervisor.stop());
