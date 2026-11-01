import { contextBridge, ipcRenderer } from "electron";
import { IPC, type EngineState, type FileFilter, type SiegeSenseApi } from "./api";

const api: SiegeSenseApi = {
  getEngine: () => ipcRenderer.invoke(IPC.engineGet),
  onEngineState: (cb) => {
    const listener = (_: unknown, s: EngineState) => cb(s);
    ipcRenderer.on(IPC.engineState, listener);
    return () => ipcRenderer.removeListener(IPC.engineState, listener);
  },
  pickFile: (filters?: FileFilter[]) => ipcRenderer.invoke(IPC.pickFile, filters),
  platform: process.platform,
};

contextBridge.exposeInMainWorld("siegesense", api);
