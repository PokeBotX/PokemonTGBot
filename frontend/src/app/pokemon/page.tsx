"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { InfoRow } from "@/components/info-row";
import { PageHeader } from "@/components/page-header";
import { SectionCard } from "@/components/section-card";
import { TopHeader } from "@/components/top-header";
import { Button } from "@/components/ui/button";
import { normalizePokemonRarity } from "@/components/pokemon-rarity";
import { PokemonTypeIcons } from "@/components/pokemon-type-icon";
import {
  usePokemonDetail,
  usePokemonImageCycle,
  usePokemonLockToggle,
} from "@/hooks/use-pokemon-detail";

function PokemonDetailScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const userPokemonId = useMemo(() => {
    const raw = searchParams.get("id");
    if (!raw) {
      return null;
    }
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  const detailQuery = usePokemonDetail(userPokemonId);
  const lockMutation = usePokemonLockToggle(userPokemonId);
  const imageMutation = usePokemonImageCycle(userPokemonId);
  const data = detailQuery.data;

  const handleBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }
    router.push("/");
  };

  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
    >
      <TopHeader />

      {userPokemonId === null ? (
        <EmptyState
          icon="📘"
          title="Покемон не выбран"
          description="Открой карточку из коллекции или избранного."
        />
      ) : detailQuery.isLoading ? (
        <SectionCard>
          <div className="animate-pulse space-y-4">
            <div className="mx-auto h-40 w-40 rounded-3xl bg-slate-700" />
            <div className="h-6 rounded bg-slate-700" />
            <div className="h-20 rounded bg-slate-800" />
          </div>
        </SectionCard>
      ) : detailQuery.isError || !data ? (
        <ErrorState
          icon="📘"
          title="Не удалось загрузить карточку"
          description="Попробуй открыть покемона ещё раз чуть позже."
        />
      ) : (
        <>
          <SectionCard>
            <PageHeader
              eyebrow={`#${data.id}`}
              title={data.name}
              description={`Редкость: ${normalizePokemonRarity(data.rarity).toUpperCase()}`}
            />

            <div className="mt-5">
              {data.imageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={data.imageUrl}
                  alt={data.name}
                  className="mx-auto h-40 w-40 rounded-3xl object-cover"
                />
              ) : (
                <div className="mx-auto h-40 w-40 rounded-3xl bg-slate-700" />
              )}
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <PokemonTypeIcons types={data.type} iconClassName="h-5 w-5" />
                <span className="text-sm text-slate-300">{data.type}</span>
              </div>
              <span className="text-sm text-slate-400">
                Экземпляр #{data.userPokemonId}
              </span>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <Button
                type="button"
                variant="secondary"
                className="rounded-xl bg-slate-700 text-slate-100 hover:bg-slate-600"
                onClick={() => void lockMutation.mutateAsync()}
                disabled={lockMutation.isPending}
              >
                {lockMutation.isPending
                  ? "Сохраняем..."
                  : data.isLocked
                    ? "🔓 Разлочить"
                    : "🔒 Залочить"}
              </Button>
              {data.imageVariant.canSwitch ? (
                <Button
                  type="button"
                  variant="secondary"
                  className="rounded-xl bg-slate-700 text-slate-100 hover:bg-slate-600"
                  onClick={() => void imageMutation.mutateAsync()}
                  disabled={imageMutation.isPending}
                >
                  {imageMutation.isPending
                    ? "Переключаем..."
                    : `🖼 ${data.imageVariant.position}/${data.imageVariant.total}`}
                </Button>
              ) : null}
            </div>

            {data.sourceUrl ? (
              <div className="mt-3">
                <a
                  href={data.sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-cyan-300 underline underline-offset-4"
                >
                  🔗 Источник
                </a>
              </div>
            ) : null}
          </SectionCard>

          <SectionCard title="Характеристики">
            <div className="space-y-3">
              <InfoRow label="Количество" value={data.quantity} />
              <InfoRow label="HP" value={data.baseHp} />
              <InfoRow label="ATK" value={data.baseAttack} />
              <InfoRow label="DEF" value={data.baseDefense} />
              <InfoRow label="SPD" value={data.baseStamina} />
              <InfoRow label="Статус" value={data.isLocked ? "Залочен" : "Не залочен"} />
            </div>
          </SectionCard>

          <Button
            type="button"
            variant="ghost"
            className="justify-start rounded-xl px-0 text-slate-300 hover:bg-transparent hover:text-white"
            onClick={handleBack}
          >
            ← Назад к списку
          </Button>
        </>
      )}
    </AppShell>
  );
}

export default function PokemonDetailPage() {
  return (
    <Suspense
      fallback={
        <AppShell
          className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
          navVariant="minimal"
        >
          <TopHeader />
          <SectionCard>
            <div className="animate-pulse space-y-4">
              <div className="mx-auto h-40 w-40 rounded-3xl bg-slate-700" />
              <div className="h-6 rounded bg-slate-700" />
              <div className="h-20 rounded bg-slate-800" />
            </div>
          </SectionCard>
        </AppShell>
      }
    >
      <PokemonDetailScreen />
    </Suspense>
  );
}
