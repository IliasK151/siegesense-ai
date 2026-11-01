import { create } from "zustand";

export type Page = "home" | "warmup" | "live" | "review" | "progress" | "settings" | "setup";

type NavState = { page: Page; go: (page: Page) => void };

export const useNav = create<NavState>((set) => ({
  page: "home",
  go: (page) => set({ page }),
}));
