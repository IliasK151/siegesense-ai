import { join } from "node:path";
import { app, BrowserWindow, dialog, ipcMain } from "electron";
import { IPC, type EngineConnection, type EngineState, type FileFilter } from "../preload/api";
import { EngineSupervisor, resolveEngineCommand } from "./engineProcess";

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
  win.webContents.on("did-finish-load", () => win?.webContents.send(IPC.engineState, lastState));
  if (process.env.ELECTRON_RENDERER_URL) void win.loadURL(process.env.ELECTRON_RENDERER_URL);
  else void win.loadFile(join(__dirname, "../renderer/index.html"));
}

void app.whenReady().then(() => {
  createWindow();
  supervisor.start().catch(() => {
    /* state "failed" is already forwarded to the renderer */
  });
});

app.on("window-all-closed", () => app.quit());
app.on("before-quit", () => supervisor.stop());
