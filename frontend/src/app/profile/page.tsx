import { AppShell } from "@/components/app-shell";
import { ProfileCard } from "@/components/profile-card";
import { TopHeader } from "@/components/top-header";

export default function ProfilePage() {
  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
      showScrollToTop
    >
      <TopHeader />
      <ProfileCard />
    </AppShell>
  );
}
