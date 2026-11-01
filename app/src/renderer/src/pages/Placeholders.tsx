import { ChartLine, Clapperboard } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "./PageHeader";

export function Review() {
  return (
    <>
      <PageHeader title="Session Review" subtitle="Round timelines, death clips and coach notes." />
      <EmptyState icon={Clapperboard} title="No sessions yet">
        Once Live Mode is ready, every match you play shows up here with clips of each death.
      </EmptyState>
    </>
  );
}

export function Progress() {
  return (
    <>
      <PageHeader title="Progress" subtitle="How your habits change over time." />
      <EmptyState icon={ChartLine} title="Nothing to chart yet">
        Play a few sessions and your overshoot, reaction time and survival trends will appear here.
      </EmptyState>
    </>
  );
}
