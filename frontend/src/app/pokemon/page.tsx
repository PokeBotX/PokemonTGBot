"use client";

import { Suspense, useMemo, useState } from "react";
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
  usePokemonInstances,
  usePokemonRelease,
  usePokemonSell,
  usePokemonSellPrecheck,
  usePokemonLockToggle,
} from "@/hooks/use-pokemon-detail";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronLeft, DoorOpen, Heart, ShoppingCart } from "lucide-react";

const STAT_MAX = {
  hp: 255,
  atk: 181,
  def: 230,
  spd: 200,
} as const;

function PokemonDetailScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [activeDialog, setActiveDialog] = useState<"sell" | "release" | null>(null);
  const [instancesOpen, setInstancesOpen] = useState(false);
  const [sellPrice, setSellPrice] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
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
  const instancesQuery = usePokemonInstances(userPokemonId);
  const releaseMutation = usePokemonRelease(userPokemonId);
  const sellMutation = usePokemonSell(userPokemonId);
  const sellPrecheckMutation = usePokemonSellPrecheck(userPokemonId);
  const data = detailQuery.data;

  const handleBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }
    router.push("/");
  };

  const closeDialog = () => {
    setActiveDialog(null);
    setActionError(null);
  };

  const handleOpenDialog = async (dialog: "sell" | "release") => {
    if (dialog === "sell") {
      setActionError(null);
      setActionSuccess(null);
      try {
        const precheck = await sellPrecheckMutation.mutateAsync();
        if (!precheck.ok) {
          setActiveDialog(null);
          setActionError(precheck.error ?? "Все слоты для продажи заняты.");
          return;
        }
      } catch (error) {
        setActiveDialog(null);
        setActionError(error instanceof Error ? error.message : "Не удалось проверить продажу.");
        return;
      }
    }
    setActiveDialog(dialog);
    setActionError(null);
    setActionSuccess(null);
  };

  const handleRelease = async () => {
    setActionError(null);
    try {
      const result = await releaseMutation.mutateAsync();
      setActionSuccess(`Покемон отпущен. Получено ${result.rewardAmount} PokéDollar.`);
      setActiveDialog(null);
      router.push("/");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось отпустить покемона.");
    }
  };

  const handleSell = async () => {
    const parsedPrice = Number(sellPrice.trim());
    if (!Number.isInteger(parsedPrice) || parsedPrice <= 0) {
      setActionError("Введите цену лота больше нуля.");
      return;
    }

    setActionError(null);
    try {
      const result = await sellMutation.mutateAsync(parsedPrice);
      setActionSuccess(`Лот создан за ${result.price} PokéDollar.`);
      setActiveDialog(null);
      router.push("/shop?tab=listings");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось выставить покемона на рынок.");
    }
  };

  const isActionBlocked = Boolean(data?.isLocked || data?.isInPvpTeam);
  const instanceEntries = instancesQuery.data?.entries ?? [];
  const canSwitchInstances = instanceEntries.length > 1;
  const statusLabel = data
    ? data.isLocked && data.isInPvpTeam
      ? "В Избранном • В Боевой Команде"
      : data.isLocked
        ? "В Избранном"
        : data.isInPvpTeam
          ? "В Боевой Команде"
          : "Не в Избранном"
    : "Не в Избранном";

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
              <PageHeader
                eyebrow={`#${formatPokemonDisplayId(data.id, data.dexFormCode)}`}
                title={formatPokemonDisplayName(data.name, data.formBadge)}
                description={
                  data.formBadge
                    ? `Редкость: ${normalizePokemonRarity(data.rarity).toUpperCase()} • Форма: ${data.formBadge}`
                    : `Редкость: ${normalizePokemonRarity(data.rarity).toUpperCase()}`
                }
              />
              <Button
                type="button"
                variant="secondary"
                size="icon-sm"
                className="absolute right-0 top-0 z-20 rounded-full border border-slate-700 bg-slate-800/95 text-slate-100 shadow-[0_8px_20px_rgba(15,23,42,0.35)] backdrop-blur hover:bg-slate-700"
                onClick={handleBack}
                aria-label="Назад к списку"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
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
              <button
                type="button"
                className={cn(
                  "inline-flex items-center gap-1 text-sm font-medium text-slate-200",
                  canSwitchInstances
                    ? "transition hover:text-white"
                    : "cursor-default text-slate-400",
                )}
                onClick={() => {
                  if (canSwitchInstances) {
                    setInstancesOpen(true);
                  }
                }}
                disabled={!canSwitchInstances}
              >
                <span>Экземпляр #{data.userPokemonId}</span>
                {canSwitchInstances ? <ChevronDown className="h-4 w-4" /> : null}
              </button>
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
                <Heart className={cn("h-4 w-4", data.isLocked && "fill-current")} />
                {lockMutation.isPending
                  ? "Сохраняем..."
                  : data.isLocked
                    ? "Убрать из Избранного"
                    : "В Избранное"}
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

            <div className="mt-3 grid grid-cols-2 gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  className={cn(
                    "rounded-xl border border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700",
                    isActionBlocked && "cursor-not-allowed border-slate-800 bg-slate-900 text-slate-500 hover:bg-slate-900",
                  )}
                  disabled={isActionBlocked}
                  onClick={() => void handleOpenDialog("sell")}
                >
                  <ShoppingCart className="h-4 w-4" />
                  Продать
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  className={cn(
                  "rounded-xl border border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700",
                  isActionBlocked && "cursor-not-allowed border-slate-800 bg-slate-900 text-slate-500 hover:bg-slate-900",
                  )}
                  disabled={isActionBlocked}
                  onClick={() => void handleOpenDialog("release")}
                >
                  <DoorOpen className="h-4 w-4" />
                  Отпустить
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
              <InfoRow label="Количество" value={data.quantity} />
              <InfoRow label="Статус" value={statusLabel} />
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

          {activeDialog ? (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm">
              <div className="w-full max-w-md rounded-3xl border border-slate-700 bg-slate-900 p-5 shadow-[0_24px_80px_rgba(2,6,23,0.7)]">
                <div className="space-y-4">
                  <div>
                    <h3 className="text-lg font-semibold text-white">
                      {activeDialog === "sell" ? "Подтверждение продажи" : "Подтверждение отпуска"}
                    </h3>
                  </div>

                  {activeDialog === "sell" ? (
                    <>
                      <p className="text-sm leading-relaxed text-slate-300">
                        Укажи цену лота для
                        {" "}
                        <span className="font-semibold text-white">
                          {formatPokemonDisplayName(data.name, data.formBadge)}
                        </span>
                        .
                      </p>
                      <input
                        type="number"
                        min={1}
                        inputMode="numeric"
                        value={sellPrice}
                        onChange={(event) => setSellPrice(event.target.value)}
                        placeholder="Например, 500"
                        className="h-11 w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 text-sm text-slate-100 outline-none transition focus:border-cyan-400"
                      />
                      <p className="text-xs text-slate-400">
                        Комиссия и остальные ограничения останутся такими же, как в боте.
                      </p>
                    </>
                  ) : (
                    <p className="text-sm leading-relaxed text-slate-300">
                      Отпустить
                      {" "}
                      <span className="font-semibold text-white">
                        {formatPokemonDisplayName(data.name, data.formBadge)}
                      </span>
                      ?
                      {" "}
                      После подтверждения экземпляр исчезнет из коллекции навсегда.
                    </p>
                  )}

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
                      disabled={sellMutation.isPending || releaseMutation.isPending}
                    >
                      Назад
                    </Button>
                    <Button
                      type="button"
                      variant={activeDialog === "sell" ? "secondary" : "destructive"}
                      className={cn(
                        "flex-1 rounded-xl",
                        activeDialog === "sell"
                          ? "bg-amber-500/15 text-amber-200 hover:bg-amber-500/25"
                          : "",
                      )}
                      onClick={activeDialog === "sell" ? handleSell : handleRelease}
                      disabled={sellMutation.isPending || releaseMutation.isPending}
                    >
                      {sellMutation.isPending || releaseMutation.isPending
                        ? "Подтверждаем..."
                        : activeDialog === "sell"
                          ? "Подтвердить продажу"
                          : "Подтвердить отпуск"}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {instancesOpen ? (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 backdrop-blur-sm">
              <div className="w-full max-w-md rounded-3xl border border-slate-700 bg-slate-900 p-5 shadow-[0_24px_80px_rgba(2,6,23,0.7)]">
                <div className="space-y-4">
                  <div>
                    <h3 className="text-lg font-semibold text-white">Выберите экземпляр</h3>
                    <p className="mt-1 text-sm text-slate-400">
                      Так ты сможешь точно выбрать, какого покемона продавать или отпускать.
                    </p>
                  </div>

                  {instancesQuery.isLoading ? (
                    <div className="space-y-2">
                      <div className="h-11 rounded-2xl bg-slate-800" />
                      <div className="h-11 rounded-2xl bg-slate-800" />
                    </div>
                  ) : (
                    <div className="max-h-[48vh] space-y-2 overflow-y-auto pr-1">
                      {instanceEntries.map((instance) => {
                        const isCurrent = instance.userPokemonId === data.userPokemonId;
                        return (
                          <button
                            key={instance.userPokemonId}
                            type="button"
                            className={cn(
                              "flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition",
                              isCurrent
                                ? "border-cyan-400/40 bg-cyan-400/10"
                                : "border-slate-700 bg-slate-950 hover:border-slate-500 hover:bg-slate-800",
                            )}
                            onClick={() => {
                              setInstancesOpen(false);
                              if (!isCurrent) {
                                router.replace(`/pokemon?id=${instance.userPokemonId}`);
                              }
                            }}
                          >
                            <div>
                              <p className="text-sm font-medium text-white">
                                Экземпляр #{instance.userPokemonId}
                              </p>
                              <p className="mt-1 text-xs text-slate-400">
                                {instance.isLocked ? "В Избранном" : "Не в Избранном"}
                                {instance.isInPvpTeam ? " • В Боевой Команде" : ""}
                              </p>
                            </div>
                            <div className="text-right text-xs text-slate-400">
                              {instance.formBadge ? (
                                <p>{instance.formBadge}</p>
                              ) : null}
                              {isCurrent ? <p className="text-cyan-300">Текущий</p> : null}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}

                  <Button
                    type="button"
                    variant="secondary"
                    className="w-full rounded-xl bg-slate-800 text-slate-100 hover:bg-slate-700"
                    onClick={() => setInstancesOpen(false)}
                  >
                    Закрыть
                  </Button>
                </div>
              </div>
            </div>
          ) : null}

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
