"use client";

import { Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { InfoRow } from "@/components/info-row";
import { PageHeader } from "@/components/page-header";
import { ProgressInfoRow } from "@/components/progress-info-row";
import { SectionCard } from "@/components/section-card";
import { TopHeader } from "@/components/top-header";
import { Button } from "@/components/ui/button";
import { formatPokemonDisplayId, formatPokemonDisplayName } from "@/lib/pokemon-display";
import { normalizePokemonRarity } from "@/components/pokemon-rarity";
import { PokemonFormBadge } from "@/components/pokemon-form-badge";
import { PokemonTypeIcons } from "@/components/pokemon-type-icon";
import {
  usePokemonDetail,
  usePokemonImageCycle,
  usePokemonLockToggle,
} from "@/hooks/use-pokemon-detail";
import { ChevronLeft } from "lucide-react";

const STAT_MAX = {
  hp: 255,
  atk: 181,
  def: 230,
  spd: 200,
} as const;

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
            <div className="relative">
              <Button
                type="button"
                variant="secondary"
                size="icon-sm"
                className="absolute right-0 top-0 z-10 rounded-full border border-slate-700 bg-slate-800/95 text-slate-100 shadow-[0_8px_20px_rgba(15,23,42,0.35)] hover:bg-slate-700"
                onClick={handleBack}
                aria-label="Назад к списку"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>

              <PageHeader
                eyebrow={`#${formatPokemonDisplayId(data.id, data.dexFormCode)}`}
                title={formatPokemonDisplayName(data.name, data.formBadge)}
                description={
                  data.formBadge
                    ? `Редкость: ${normalizePokemonRarity(data.rarity).toUpperCase()} • Форма: ${data.formBadge}`
                    : `Редкость: ${normalizePokemonRarity(data.rarity).toUpperCase()}`
                }
              />
            </div>

            <div className="mt-5">
              {data.imageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={data.imageUrl}
                  alt={formatPokemonDisplayName(data.name, data.formBadge)}
                  className="mx-auto h-52 w-52 rounded-3xl object-cover"
                />
              ) : (
                <div className="mx-auto h-52 w-52 rounded-3xl bg-slate-700" />
              )}
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <PokemonTypeIcons types={data.type} iconClassName="h-5 w-5" />
                <span className="text-sm text-slate-300">{data.type}</span>
              </div>
              <span className="text-sm font-medium text-slate-200">
                Экземпляр #{data.userPokemonId}
              </span>
            </div>

            {data.formBadge ? (
              <div className="mt-3">
                <PokemonFormBadge formBadge={data.formBadge} />
              </div>
            ) : null}

            <div className="mt-4 flex items-start gap-3">
              <Button
                type="button"
                variant="secondary"
                className="min-w-0 flex-1 whitespace-normal rounded-xl bg-slate-700 px-4 py-2 text-center leading-tight text-slate-100 hover:bg-slate-600"
                onClick={() => void lockMutation.mutateAsync()}
                disabled={lockMutation.isPending}
              >
                {lockMutation.isPending
                  ? "Сохраняем..."
                  : data.isLocked
                    ? "🔓 Убрать из Избранного"
                    : "🔒 В Избранное"}
              </Button>
              {data.imageVariant.canSwitch ? (
                <Button
                  type="button"
                  variant="secondary"
                  className="shrink-0 rounded-xl bg-slate-700 text-slate-100 hover:bg-slate-600"
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
              <InfoRow
                label="Статус"
                value={data.isLocked ? "В Избранном" : "Не в Избранном"}
              />
              <ProgressInfoRow
                label="HP"
                value={data.baseHp}
                percentage={(data.baseHp / STAT_MAX.hp) * 100}
                barClassName="bg-gradient-to-r from-rose-500 to-rose-300"
              />
              <ProgressInfoRow
                label="ATK"
                value={data.baseAttack}
                percentage={(data.baseAttack / STAT_MAX.atk) * 100}
                barClassName="bg-gradient-to-r from-amber-500 to-orange-300"
              />
              <ProgressInfoRow
                label="DEF"
                value={data.baseDefense}
                percentage={(data.baseDefense / STAT_MAX.def) * 100}
                barClassName="bg-gradient-to-r from-cyan-500 to-sky-300"
              />
              <ProgressInfoRow
                label="SPD"
                value={data.baseStamina}
                percentage={(data.baseStamina / STAT_MAX.spd) * 100}
                barClassName="bg-gradient-to-r from-violet-500 to-fuchsia-300"
              />
            </div>
          </SectionCard>

          <Button
            type="button"
            variant="ghost"
            className="mx-auto inline-flex items-center justify-center gap-2 rounded-xl px-0 text-slate-300 hover:bg-transparent hover:text-white"
            onClick={handleBack}
          >
            <ChevronLeft className="h-4 w-4" />
            <span>Назад к списку</span>
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
