"use client";

import { Suspense, useMemo, useState } from "react";
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
import { PokemonFormBadge } from "@/components/pokemon-form-badge";
import { PokemonTypeIcons } from "@/components/pokemon-type-icon";
import {
  useMarketDetail,
  useMarketListingPurchase,
  useMarketListingRemove,
  useMyMarketListingDetail,
} from "@/hooks/use-market-detail";
import { formatPokemonDisplayId, formatPokemonDisplayName } from "@/lib/pokemon-display";
import { cn } from "@/lib/utils";
import { ChevronLeft, ShoppingCart, XCircle } from "lucide-react";

type ListingScope = "market" | "mine";

function MarketListingDetailScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [activeDialog, setActiveDialog] = useState<"buy" | "remove" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const listingId = useMemo(() => {
    const raw = searchParams.get("id");
    if (!raw) {
      return null;
    }
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  const scope: ListingScope = searchParams.get("scope") === "mine" ? "mine" : "market";
  const isOwnListing = scope === "mine";

  const marketDetailQuery = useMarketDetail(isOwnListing ? null : listingId);
  const ownDetailQuery = useMyMarketListingDetail(isOwnListing ? listingId : null);
  const detailQuery = isOwnListing ? ownDetailQuery : marketDetailQuery;
  const data = detailQuery.data;

  const purchaseMutation = useMarketListingPurchase(isOwnListing ? null : listingId);
  const removeMutation = useMarketListingRemove(isOwnListing ? listingId : null);

  const handleBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }
    router.push(isOwnListing ? "/shop?tab=listings" : "/shop");
  };

  const closeDialog = () => {
    setActiveDialog(null);
    setActionError(null);
  };

  const handleBuy = async () => {
    setActionError(null);
    try {
      const result = await purchaseMutation.mutateAsync();
      setActionSuccess(`Покупка завершена. Потрачено 🪙 ${result.price}.`);
      setActiveDialog(null);
      router.push("/shop");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось купить лот.");
    }
  };

  const handleRemove = async () => {
    setActionError(null);
    try {
      await removeMutation.mutateAsync();
      setActionSuccess("Лот снят с продажи.");
      setActiveDialog(null);
      router.push("/shop?tab=listings");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось снять лот.");
    }
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
          description="Откройте карточку из списка рынка."
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
          description="Попробуйте открыть рынок ещё раз чуть позже."
        />
      ) : (
        <>
          <SectionCard>
            <div className="relative">
              <PageHeader
                eyebrow={`#${formatPokemonDisplayId(data.pokemonId, data.dexFormCode)} • Лот #${data.listingId}`}
                title={formatPokemonDisplayName(data.name, data.formBadge)}
                description={
                  data.formBadge
                    ? `Редкость: ${normalizePokemonRarity(data.rarity).toUpperCase()} • Форма: ${data.formBadge}`
                    : `Редкость: ${normalizePokemonRarity(data.rarity).toUpperCase()}`
                }
              />
              <div className="absolute right-0 top-0 flex items-center gap-2">
                <div className="rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-sm font-semibold text-amber-200">
                  🪙 {data.pokecoinBalance}
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  size="icon-sm"
                  className="rounded-full border border-slate-700 bg-slate-800/95 text-slate-100 shadow-[0_8px_20px_rgba(15,23,42,0.35)] backdrop-blur hover:bg-slate-700"
                  onClick={handleBack}
                  aria-label="Назад"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <div className="mt-5">
              {data.imageUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={data.imageUrl}
                  alt={formatPokemonDisplayName(data.name, data.formBadge)}
                  className="mx-auto h-[44vh] max-h-[520px] min-h-[280px] w-full rounded-3xl object-contain"
                />
              ) : (
                <div className="mx-auto h-[44vh] max-h-[520px] min-h-[280px] w-full rounded-3xl bg-slate-700" />
              )}
            </div>

            <div className="mt-4 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <PokemonTypeIcons types={data.type} iconClassName="h-5 w-5" />
                <span className="text-sm text-slate-300">{data.type}</span>
              </div>
              <span className="text-sm text-slate-400">
                #{formatPokemonDisplayId(data.pokemonId, data.dexFormCode)}
              </span>
            </div>

            {data.formBadge ? (
              <div className="mt-3">
                <PokemonFormBadge formBadge={data.formBadge} />
              </div>
            ) : null}

            <div className="mt-4 space-y-3 rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm">
              <InfoRow label="Цена" value={`🪙 ${data.price}`} />
              <InfoRow label={isOwnListing ? "Продавец" : "Продавец"} value={data.sellerLabel} />
              <InfoRow label="Осталось" value={`${data.daysRemaining} дн.`} />
            </div>

            <div className="mt-4">
              <Button
                type="button"
                variant={isOwnListing ? "secondary" : "default"}
                className={cn(
                  "w-full rounded-xl",
                  isOwnListing
                    ? "border border-rose-500/30 bg-rose-500/10 text-rose-200 hover:bg-rose-500/20"
                    : "bg-cyan-300 text-slate-950 hover:bg-cyan-200",
                )}
                onClick={() => {
                  setActionError(null);
                  setActionSuccess(null);
                  if (!isOwnListing && data.pokecoinBalance < data.price) {
                    setActiveDialog(null);
                    setActionError("Недостаточно pokecoin для покупки.");
                    return;
                  }
                  setActiveDialog(isOwnListing ? "remove" : "buy");
                }}
                disabled={purchaseMutation.isPending || removeMutation.isPending}
              >
                {isOwnListing ? (
                  <>
                    <XCircle className="h-4 w-4" />
                    Снять лот
                  </>
                ) : (
                  <>
                    <ShoppingCart className="h-4 w-4" />
                    Купить
                  </>
                )}
              </Button>
            </div>

            {actionSuccess ? (
              <div className="mt-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                {actionSuccess}
              </div>
            ) : null}

            {actionError && !activeDialog ? (
              <div className="mt-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                {actionError}
              </div>
            ) : null}

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

          {activeDialog ? (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm">
              <div className="w-full max-w-md rounded-3xl border border-slate-700 bg-slate-900 p-5 shadow-[0_24px_80px_rgba(2,6,23,0.7)]">
                <div className="space-y-4">
                  <div>
                    <h3 className="text-lg font-semibold text-white">
                      {activeDialog === "buy" ? "Подтверждение покупки" : "Снять лот"}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-slate-300">
                      {activeDialog === "buy" ? (
                        <>
                          Купить
                          {" "}
                          <span className="font-semibold text-white">
                            {formatPokemonDisplayName(data.name, data.formBadge)}
                          </span>
                          {" "}за{" "}
                          <span className="font-semibold text-amber-200">🪙 {data.price}</span>?
                        </>
                      ) : (
                        <>
                          Снять с продажи
                          {" "}
                          <span className="font-semibold text-white">
                            {formatPokemonDisplayName(data.name, data.formBadge)}
                          </span>
                          ?
                        </>
                      )}
                    </p>
                  </div>

                  {actionError ? (
                    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                      {actionError}
                    </div>
                  ) : null}

                  <div className="flex gap-3">
                    <Button
                      type="button"
                      variant="secondary"
                      className="flex-1 rounded-xl bg-slate-800 text-slate-100 hover:bg-slate-700"
                      onClick={closeDialog}
                      disabled={purchaseMutation.isPending || removeMutation.isPending}
                    >
                      Назад
                    </Button>
                    <Button
                      type="button"
                      variant={activeDialog === "buy" ? "default" : "secondary"}
                      className={cn(
                        "flex-1 rounded-xl",
                        activeDialog === "buy"
                          ? "bg-cyan-300 text-slate-950 hover:bg-cyan-200"
                          : "border border-rose-500/30 bg-rose-500/10 text-rose-200 hover:bg-rose-500/20",
                      )}
                      onClick={activeDialog === "buy" ? handleBuy : handleRemove}
                      disabled={purchaseMutation.isPending || removeMutation.isPending}
                    >
                      {purchaseMutation.isPending || removeMutation.isPending
                        ? "Подтверждаем..."
                        : activeDialog === "buy"
                          ? "Подтвердить покупку"
                          : "Подтвердить снятие"}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          <Button
            type="button"
            variant="ghost"
            className="justify-start rounded-xl px-0 text-slate-300 hover:bg-transparent hover:text-white"
            onClick={handleBack}
          >
            ← Назад
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
