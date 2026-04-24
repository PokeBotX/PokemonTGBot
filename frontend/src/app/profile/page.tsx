import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { ProfileCard } from "@/components/profile-card";

export default function ProfilePage() {
  return (
    <AppShell>
      <PageHeader
        eyebrow="Профиль"
        title="Твой профиль"
        description="Здесь собрана информация о тренере и прогрессе."
      />

      <ProfileCard />
    </AppShell>
  );
}
