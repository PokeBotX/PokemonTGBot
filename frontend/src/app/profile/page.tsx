import { AppShell } from "@/components/app-shell";
import { ProfileCard } from "@/components/profile-card";
import { TopHeader } from "@/components/top-header";

export default function ProfilePage() {
  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
    >
      <TopHeader />
      <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-4">
        <p className="text-sm text-slate-400">Профиль</p>
        <h1 className="mt-2 text-2xl font-bold text-white">Тренер</h1>
        <p className="mt-2 text-sm text-slate-300">
          Здесь показывается тот же прогресс, что и в Telegram-профиле, но в Mini App формате.
        </p>
      </div>
      <ProfileCard />
    </AppShell>
  );
}
