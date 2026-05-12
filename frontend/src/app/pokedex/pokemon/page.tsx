"use client";

import { Suspense, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { InfoRow } from "@/components/info-row";
import { PageHeader } from "@/components/page-header";
import { PokemonFormBadge } from "@/components/pokemon-form-badge";
import { PokemonTypeIcons } from "@/components/pokemon-type-icon";
import { normalizePokemonRarity } from "@/components/pokemon-rarity";
import { SectionCard } from "@/components/section-card";
import { TopHeader } from "@/components/top-header";
import { Button } from "@/components/ui/button";
import { usePokedexBuyRequestCreate, usePokedexBuyRequestPrecheck, usePokedexDetail } from "@/hooks/use-pokedex";
import { formatPokemonDisplayId, formatPokemonDisplayName } from "@/lib/pokemon-display";
import { ChevronLeft, ShoppingCart } from "lucide-react";

function PokedexPokemonDetailScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [price, setPrice] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const pokemonId = useMemo(() => {
    const raw = searchParams.get("id");
    if (!raw) {
      return null;
    }
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  const detailQuery = usePokedexDetail(pokemonId);
  const precheckMutation = usePokedexBuyRequestPrecheck(pokemonId);
  const createMutation = usePokedexBuyRequestCreate(pokemonId);
  const data = detailQuery.data;

  const handleBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }
    router.push("/pokedex");
  };

  const handleOpenRequest = async () => {
    setActionError(null);
    setActionSuccess(null);
    try {
      const precheck = await precheckMutation.mutateAsync();
      if (!precheck.ok) {
        setConfirmOpen(false);
        setActionError(precheck.error ?? "Нельзя создать заявку сейчас.");
        return;
      }
      setConfirmOpen(true);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось проверить заявку.");
    }
  };

  const handleCreateRequest = async () => {
    const parsedPrice = Number(price.trim());
    if (!Number.isInteger(parsedPrice) || parsedPrice <= 0) {
      setActionError("Введите цену заявки больше нуля.");
      return;
    }
    if (data && parsedPrice > data.pokecoinBalance) {
      setActionError("Недостаточно pokecoin для заявки.");
      return;
    }

    setActionError(null);
    try {
      const result = await createMutation.mutateAsync(parsedPrice);
      setActionSuccess(`Заявка создана. Зарезервировано 🪙 ${result.reservedAmount}.`);
      setConfirmOpen(false);
      router.push("/shop?tab=requests");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось создать заявку.");
    }
  };

  const relatedLabel = data?.relatedForms.length
    ? data.relatedForms
        .map((related) => related.formBadge ?? "Базовая")
        .join(", ")
    : null;

  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
    >
      <TopHeader />

      {pokemonId === null ? (
        <EmptyState
          icon="📘"
          title="Покемон не выбран"
          description="Открой запись из покедекса."
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
          title="Не удалось загрузить запись покедекса"
          description="Попробуй открыть её ещё раз чуть позже."
        />
      ) : (
        <>
          <SectionCard>
            <div className="relative">
              <PageHeader
                eyebrow={`#${formatPokemonDisplayId(data.id, data.dexFormCode)}`}
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
              <span className="rounded-full border border-slate-700 bg-slate-900/80 px-3 py-1 text-xs font-semibold text-slate-200">
                {data.isCollected ? "Есть" : "Нет"}
              </span>
            </div>

            {data.formBadge ? (
              <div className="mt-3">
                <PokemonFormBadge formBadge={data.formBadge} />
              </div>
            ) : null}

            <div className="mt-4 space-y-3 rounded-2xl border border-slate-800 bg-slate-950/70 px-4 py-3 text-sm">
              <InfoRow label="Статус" value={data.isCollected ? "Есть в коллекции" : "Ещё не собран"} />
              {relatedLabel ? <InfoRow label="Другие формы" value={relatedLabel} /> : null}
            </div>

            <div className="mt-4">
              <Button
                type="button"
                variant="secondary"
                className="w-full rounded-xl bg-cyan-300 text-slate-950 hover:bg-cyan-200"
                onClick={() => void handleOpenRequest()}
                disabled={precheckMutation.isPending || createMutation.isPending}
              >
                <ShoppingCart className="h-4 w-4" />
                Оставить заявку на покупку
              </Button>
            </div>

            {actionSuccess ? (
              <div className="mt-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                {actionSuccess}
              </div>
            ) : null}

            {actionError && !confirmOpen ? (
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

          {confirmOpen ? (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm">
              <div className="w-full max-w-md rounded-3xl border border-slate-700 bg-slate-900 p-5 shadow-[0_24px_80px_rgba(2,6,23,0.7)]">
                <div className="space-y-4">
                  <div>
                    <h3 className="text-lg font-semibold text-white">Заявка на покупку</h3>
                    <p className="mt-2 text-sm leading-relaxed text-slate-300">
                      Укажи, сколько pokecoin ты готов зарезервировать на
                      {" "}
                      <span className="font-semibold text-white">
                        {formatPokemonDisplayName(data.name, data.formBadge)}
                      </span>.
                    </p>
                  </div>

                  <label className="block">
                    <span className="mb-2 block text-sm font-medium text-slate-200">Цена заявки</span>
                    <input
                      inputMode="numeric"
                      value={price}
                      onChange={(event) => setPrice(event.target.value)}
                      placeholder={`Максимум 🪙 ${data.pokecoinBalance}`}
                      className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-400"
                    />
                  </label>

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
                      onClick={() => setConfirmOpen(false)}
                      disabled={createMutation.isPending}
                    >
                      Назад
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      className="flex-1 rounded-xl bg-cyan-300 text-slate-950 hover:bg-cyan-200"
                      onClick={() => void handleCreateRequest()}
                      disabled={createMutation.isPending}
                    >
                      {createMutation.isPending ? "Создаём..." : "Подтвердить"}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </>
      )}
    </AppShell>
  );
}

export default function PokedexPokemonPage() {
  return (
    <Suspense
      fallback={
        <AppShell
          className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
          navVariant="minimal"
        >
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
      <PokedexPokemonDetailScreen />
    </Suspense>
  );
}
