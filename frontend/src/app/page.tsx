import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { TelegramUserCard } from "@/components/telegram-user-card";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <AppShell>
      <div>
        <p className="text-sm text-slate-400">Telegram Mini App</p>
        <h1 className="mt-2 text-3xl font-bold">PokéCollect</h1>
        <p className="mt-3 text-slate-300">
          Лови, собирай и прокачивай покемонов прямо в Telegram.
        </p>
      </div>

      <TelegramUserCard />

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
