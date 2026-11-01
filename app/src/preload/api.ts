// The API the preload script exposes to the renderer as `window.siegesense`.
export type EngineConnection = { port: number; token: string };
export type EngineState = {
  phase: "starting" | "ready" | "restarting" | "failed";
  message?: string;
};
export type FileFilter = { name: string; extensions: string[] };

export interface SiegeSenseApi {
  getEngine(): Promise<EngineConnection>;
  onEngineState(cb: (s: EngineState) => void): () => void;
  pickFile(filters?: FileFilter[]): Promise<string | null>;
  platform: string;
}

export const IPC = {
  engineGet: "engine:get",
  engineState: "engine:state",
  pickFile: "dialog:pickFile",
} as const;
