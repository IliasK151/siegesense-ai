import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useProfile } from "@/lib/engineContext";
import { useNav } from "@/store/nav";
import { PageHeader } from "./PageHeader";
import { ProfileSummary } from "./ProfileSummary";

export function Settings() {
  const { profile } = useProfile();
  const go = useNav((s) => s.go);
  return (
    <>
      <PageHeader title="Settings" subtitle="Your profile and app preferences." />
      <Card
        title={profile ? `Profile · ${profile.in_game_name}` : "Profile"}
        action={
          <Button size="sm" icon={RotateCcw} onClick={() => go("setup")}>
            Re-run setup
          </Button>
        }
      >
        {profile && <ProfileSummary profile={profile} />}
      </Card>
    </>
  );
}
