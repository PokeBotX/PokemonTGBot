import Link from "next/link";
import { UserRound } from "lucide-react";

export function TopHeader() {
  return (
    <header className="flex items-center justify-between px-1">
      <h1 className="text-3xl font-bold tracking-tight">PokeCollectBot</h1>
      <Link
        href="/profile"
        className="rounded-full border border-slate-700 bg-slate-900 p-2 text-slate-100 transition hover:bg-slate-800"
        aria-label="Открыть профиль"
      >
        <UserRound className="h-6 w-6" />
      </Link>
    </header>
  );
}