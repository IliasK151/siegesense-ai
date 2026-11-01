import { AnimatePresence, motion } from "motion/react";
import { useEffect } from "react";
import { EngineBanner } from "@/components/shell/EngineBanner";
import { Sidebar } from "@/components/shell/Sidebar";
import { TitleBar } from "@/components/shell/TitleBar";
import { type EngineLike, EngineProvider, useProfile } from "@/lib/engineContext";
import { Home } from "@/pages/Home";
import { Live } from "@/pages/Live";
import { Progress, Review } from "@/pages/Placeholders";
import { Settings } from "@/pages/Settings";
import { Warmup } from "@/pages/Warmup";
import { SetupWizard } from "@/pages/setup/SetupWizard";
import { type Page, useNav } from "@/store/nav";
import type { SiegeSenseApi } from "../../preload/api";

const pages: Record<Exclude<Page, "setup">, () => React.JSX.Element> = {
  home: Home,
  warmup: Warmup,
  live: Live,
  review: Review,
  progress: Progress,
  settings: Settings,
};

function Shell() {
  const { page, go } = useNav();
  const { profile, loading } = useProfile();

  useEffect(() => {
    if (!loading && profile === null && page !== "setup") go("setup");
  }, [loading, profile, page, go]);

  if (page === "setup") {
    return (
      <div className="flex h-full flex-col">
        <TitleBar />
        <EngineBanner />
        <SetupWizard />
      </div>
    );
  }

  const Current = pages[page];
  return (
    <div className="flex h-full flex-col">
      <TitleBar />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main className="flex min-w-0 flex-1 flex-col">
          <EngineBanner />
          <div className="min-h-0 flex-1 overflow-y-auto">
            <AnimatePresence mode="wait">
              <motion.div
                key={page}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.22, ease: "easeOut" }}
                className="mx-auto max-w-6xl px-8 py-8"
              >
                {loading ? null : <Current />}
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  );
}

type RootProps = { client?: EngineLike; onEngineState?: SiegeSenseApi["onEngineState"] };

export function Root({ client, onEngineState }: RootProps) {
  return (
    <EngineProvider client={client} onEngineState={onEngineState}>
      <Shell />
    </EngineProvider>
  );
}

export default function App() {
  return <Root />;
}
