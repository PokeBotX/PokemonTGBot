"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ErrorState } from "@/components/error-state";
import { ProgressInfoRow } from "@/components/progress-info-row";
import { ProfileCardSkeleton } from "@/components/profile-card-skeleton";
import { getTelegramWebApp } from "@/lib/telegram";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useProfile } from "@/hooks/use-profile";

function getRarityProgressClass(rarity: string) {
  switch (rarity.trim().toLowerCase()) {
    case "legendary":
      return "bg-gradient-to-r from-amber-500 to-amber-300";
    case "epic":
      return "bg-gradient-to-r from-violet-500 to-fuchsia-300";
    case "rare":
      return "bg-gradient-to-r from-emerald-500 to-emerald-300";
    case "common":
    default:
      return "bg-gradient-to-r from-stone-400 to-stone-200";
  }
}

export function ProfileCard() {
  const router = useRouter();
  const { data, isLoading, isError } = useProfile();
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  useEffect(() => {
    const syncPhoto = () => {
      const nextPhotoUrl = getTelegramWebApp()?.initDataUnsafe?.user?.photo_url ?? null;
      setPhotoUrl((current) => (current === nextPhotoUrl ? current : nextPhotoUrl));
    };

    syncPhoto();
    const intervalId = window.setInterval(syncPhoto, 500);
    window.addEventListener("focus", syncPhoto);
    window.addEventListener("visibilitychange", syncPhoto);

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", syncPhoto);
      window.removeEventListener("visibilitychange", syncPhoto);
    };
  }, []);

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
        {data.coverPokemonImageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={data.coverPokemonImageUrl}
            alt={data.coverPokemonName ?? data.name}
            className="mx-auto h-24 w-24 rounded-full object-cover ring-2 ring-slate-700"
            loading="lazy"
          />
        ) : photoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={photoUrl}
            alt={data.name}
            className="mx-auto h-24 w-24 rounded-full object-cover ring-2 ring-slate-700"
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-slate-700 text-3xl font-semibold text-slate-200">
            {data.name.slice(0, 1).toUpperCase()}
          </div>
        )}

        <div className="text-center">
          <p className="text-lg font-semibold">{data.name}</p>
          <div className="mt-1 flex items-center justify-center gap-2 text-sm text-slate-400">
            {photoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={photoUrl}
                alt={data.username ? `@${data.username}` : data.name}
                className="h-5 w-5 rounded-full object-cover ring-1 ring-slate-700"
                loading="lazy"
                referrerPolicy="no-referrer"
              />
            ) : null}
            <p>{data.username ? `@${data.username}` : "Без username"}</p>
          </div>
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
            📦 Базовый покедекс:{" "}
            <span className="font-semibold text-slate-100">{data.baseDexCount}</span> из{" "}
            <span className="font-semibold text-slate-100">{data.baseDexCatalog}</span> (
            <span className="font-semibold text-slate-100">{data.baseDexCompletionPercent}%</span>)
          </p>
          <p className="mt-2">
            🧬 Все формы:{" "}
            <span className="font-semibold text-slate-100">{data.totalFormCount}</span> из{" "}
            <span className="font-semibold text-slate-100">{data.totalFormCatalog}</span> (
            <span className="font-semibold text-slate-100">{data.totalFormCompletionPercent}%</span>)
          </p>
          <p className="mt-2 text-xs text-slate-400">
            Формы включают shiny, mega и gigantamax версии.
          </p>
          <p className="mt-2">
            ⏳ Возраст аккаунта:{" "}
            <span className="font-semibold text-slate-100">{data.accountAgeLabel}</span>
          </p>
        </div>

        <div className="space-y-2 rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3">
          {data.rarityProgress.map((progress) => (
            <ProgressInfoRow
              key={progress.rarity}
              label={progress.rarity}
              value={`${progress.ownedUnique} из ${progress.totalCatalog}`}
              percentage={progress.percent}
              barClassName={getRarityProgressClass(progress.rarity)}
            />
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
          <Button
            type="button"
            className="rounded-xl bg-slate-700 text-slate-100 hover:bg-slate-600"
            onClick={() => router.push("/pokedex")}
          >
            Всего форм: {data.totalFormCatalog}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
