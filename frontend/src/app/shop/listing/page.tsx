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
import { useMarketDetail } from "@/hooks/use-market-detail";

function MarketListingDetailScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const listingId = useMemo(() => {
    const raw = searchParams.get("id");
    if (!raw) {
      return null;
    }
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  const detailQuery = useMarketDetail(listingId);
  const data = detailQuery.data;

  const handleBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }
    router.push("/shop");
  };

  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
    >
      <TopHeader />

      {listingId === null ? (
        <EmptyState
          icon="🛒"
          title="Лот не выбран"
          description="Открой карточку из списка рынка."
        />
      ) : detailQuery.isLoading ? (
        <SectionCard>
          <div className="animate-pulse space-y-4">
            <div className="mx-auto h-40 w-40 rounded-3xl bg-slate-700" />
            <div className="h-6 rounded bg-slate-700" />
            <div className="h-24 rounded bg-slate-800" />
          </div>
        </SectionCard>
      ) : detailQuery.isError || !data ? (
        <ErrorState
          icon="🛒"
          title="Не удалось загрузить лот"
          description="Попробуй открыть рынок ещё раз чуть позже."
        />
      ) : (
        <>
          <SectionCard>
            <PageHeader
              eyebrow={`Лот #${data.listingId}`}
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
              <span className="text-sm text-slate-400">#{data.pokemonId}</span>
            </div>

            <div className="mt-4 space-y-3 rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm">
              <InfoRow label="Цена" value={`🪙 ${data.price}`} />
              <InfoRow label="Продавец" value={data.sellerLabel} />
              <InfoRow label="Осталось" value={`${data.daysRemaining} дн.`} />
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
              <InfoRow label="HP" value={data.baseHp} />
              <InfoRow label="ATK" value={data.baseAttack} />
              <InfoRow label="DEF" value={data.baseDefense} />
              <InfoRow label="SPD" value={data.baseStamina} />
            </div>
          </SectionCard>

          <Button
            type="button"
            variant="ghost"
            className="justify-start rounded-xl px-0 text-slate-300 hover:bg-transparent hover:text-white"
            onClick={handleBack}
          >
            ← Назад к рынку
          </Button>
        </>
      )}
    </AppShell>
  );
}

export default function MarketListingDetailPage() {
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
              <div className="h-24 rounded bg-slate-800" />
            </div>
          </SectionCard>
        </AppShell>
      }
    >
      <MarketListingDetailScreen />
    </Suspense>
  );
}
