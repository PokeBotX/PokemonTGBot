"use client";

import { ErrorState } from "@/components/error-state";
import { ProfileCardSkeleton } from "@/components/profile-card-skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useProfile } from "@/hooks/use-profile";

export function ProfileCard() {
  const { data, isLoading, isError } = useProfile();

  if (isLoading) {
    return <ProfileCardSkeleton />;
  }

  if (isError || !data) {
    return (
      <ErrorState
        icon="👤"
        title="Не удалось загрузить профиль"
        description="Попробуй обновить страницу чуть позже."
      />
    );
  }

  return (
    <Card className="rounded-2xl border border-slate-700 bg-slate-900 py-4 text-slate-100 shadow-[0_2px_12px_rgba(0,0,0,0.35)]">
      <CardContent className="space-y-4 px-4">
        <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-slate-700 text-2xl font-semibold text-slate-200">
          {data.name.slice(0, 1).toUpperCase()}
        </div>

        <div className="text-center">
          <p className="text-lg font-semibold">{data.name}</p>
          <p className="text-sm text-slate-400">
            {data.username ? `@${data.username}` : "Без username"}
          </p>
        </div>

        <div className="flex flex-wrap justify-center gap-2">
          <Badge className="rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-200 hover:bg-slate-700">
            {data.pokemonCount} покемонов
          </Badge>
          <Badge className="rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-200 hover:bg-slate-700">
            {data.coins} монет
          </Badge>
          <Badge className="rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-200 hover:bg-slate-700">
            {data.completionPercent}% покедекса
          </Badge>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm text-slate-300">
          <p>
            📦 У вас <span className="font-semibold text-slate-100">{data.pokemonCount}</span>{" "}
            уникальных покемонов из{" "}
            <span className="font-semibold text-slate-100">{data.totalCatalog}</span> (
            <span className="font-semibold text-slate-100">{data.completionPercent}%</span>)
          </p>
          <p className="mt-2">
            ⏳ Возраст аккаунта:{" "}
            <span className="font-semibold text-slate-100">{data.accountAgeLabel}</span>
          </p>
        </div>

        <div className="space-y-2 rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
          {data.rarityProgress.map((progress) => (
            <div key={progress.rarity} className="flex items-center justify-between gap-3 text-sm">
              <span className="text-slate-300">{progress.rarity}</span>
              <span className="text-right text-slate-100">
                {progress.ownedUnique} из {progress.totalCatalog} ({progress.percent}%)
              </span>
            </div>
          ))}
        </div>

        {data.coverPokemonName ? (
          <div className="rounded-2xl bg-slate-800 px-4 py-3 text-center text-sm text-slate-300">
            Обложка: <span className="font-medium text-slate-100">{data.coverPokemonName}</span>
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-3">
          <Button className="rounded-xl bg-slate-700 text-slate-100 hover:bg-slate-600">
            Язык: {data.language.toUpperCase()}
          </Button>
          <Button className="rounded-xl bg-slate-700 text-slate-100 hover:bg-slate-600">
            Всего видов: {data.totalCatalog}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
