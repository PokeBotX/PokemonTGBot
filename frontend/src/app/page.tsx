import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { TelegramUserCard } from "@/components/telegram-user-card";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";
import { TelegramDebugCard } from "@/components/telegram-debug-card";

export default function Home() {
  return (
    <AppShell>
      <PageHeader
        eyebrow="Telegram Mini App"
        title="PokéCollect"
        description="Лови, собирай и прокачивай покемонов прямо в Telegram."
      />

      <TelegramUserCard />

      <TelegramDebugCard />
      
      <div className="flex flex-col gap-3">
        <Link href="/profile">
          <Button className="h-14 w-full rounded-2xl bg-yellow-400 font-semibold text-slate-950 hover:bg-yellow-300">
            Открыть профиль
          </Button>
        </Link>

        <Link href="/collection">
          <Button className="h-14 w-full rounded-2xl bg-slate-800 font-semibold text-white hover:bg-slate-700">
            Открыть коллекцию
          </Button>
        </Link>
      </div>
    </AppShell>
  );
}
