import { AppShell } from "@/components/app-shell";
import { ProfileCard } from "@/components/profile-card";

export default function ProfilePage() {
  return (
    <AppShell>
      <div>
        <p className="text-sm text-slate-400">Профиль</p>
        <h1 className="mt-2 text-3xl font-bold">Твой профиль</h1>
        <p className="mt-3 text-slate-300">
          Здесь собрана информация о тренере и прогрессе.
        </p>
      </div>

      <ProfileCard />
    </AppShell>
  );
}
