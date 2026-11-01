/// <reference types="vite/client" />
import type { SiegeSenseApi } from "../../preload/api";

declare global {
  interface Window {
    siegesense?: SiegeSenseApi;
  }
}
