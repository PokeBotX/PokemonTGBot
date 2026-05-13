"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PokemonCard } from "@/components/pokemon-card";
import { PokemonListSkeleton } from "@/components/pokemon-list-skeleton";
import { TopHeader } from "@/components/top-header";
import { normalizePokemonRarity } from "@/components/pokemon-rarity";
import { usePokedex } from "@/hooks/use-pokedex";

const RARITY_OPTIONS = ["Legendary", "Epic", "Rare", "Common"] as const;
const TYPE_OPTIONS = [
  "normal",
  "fire",
  "water",
  "electric",
  "grass",
  "ice",
  "fighting",
  "poison",
  "ground",
  "flying",
  "psychic",
  "bug",
  "rock",
  "ghost",
  "dragon",
  "dark",
  "steel",
  "fairy",
] as const;
const FORM_KIND_OPTIONS = [
  { key: "shiny", label: "Shiny" },
  { key: "mega", label: "Mega" },
  { key: "gigantamax", label: "Gigantamax" },
] as const;

export function PokedexScreen() {
  const pathname = usePathname();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [rarities, setRarities] = useState<string[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [collectedState, setCollectedState] = useState<"all" | "collected" | "missing">("all");
  const [formKinds, setFormKinds] = useState<string[]>([]);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const {
    entries,
    isLoading,
    isError,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  } = usePokedex({
    query,
    rarities,
    types,
    collectedState,
    formKinds,
  });

  const restoreKey = `scroll:${pathname}:${query}:${collectedState}:${rarities.join(",")}:${types.join(",")}:${formKinds.join(",")}`;
  const activeFilterCount = useMemo(
    () =>
      rarities.length +
      types.length +
      formKinds.length +
      (collectedState !== "all" ? 1 : 0) +
      (query.trim() ? 1 : 0),
    [collectedState, formKinds.length, query, rarities.length, types.length],
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const saved = window.sessionStorage.getItem(restoreKey);
    if (!saved) {
      return;
    }

    const value = Number(saved);
    if (!Number.isFinite(value) || value < 0) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      window.scrollTo({ top: value, behavior: "auto" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [restoreKey]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const handleScroll = () => {
      window.sessionStorage.setItem(restoreKey, String(window.scrollY));
    };

    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [restoreKey]);

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !hasNextPage) {
      return;
    }

    const observer = new IntersectionObserver(
      (observerEntries) => {
        const [entry] = observerEntries;
        if (entry?.isIntersecting) {
          void fetchNextPage();
        }
      },
      { rootMargin: "240px 0px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage]);

  const toggleRarity = (rarity: string) => {
    setRarities((current) =>
      current.includes(rarity)
        ? current.filter((value) => value !== rarity)
        : [...current, rarity],
    );
  };

  const toggleType = (pokemonType: string) => {
    setTypes((current) => {
      if (current.includes(pokemonType)) {
        return current.filter((value) => value !== pokemonType);
      }
      if (current.length >= 2) {
        return current;
      }
      return [...current, pokemonType];
    });
  };

  const toggleFormKind = (formKind: string) => {
    setFormKinds((current) =>
      current.includes(formKind)
        ? current.filter((value) => value !== formKind)
        : [...current, formKind],
    );
  };

  const resetFilters = () => {
    setQuery("");
    setRarities([]);
    setTypes([]);
    setCollectedState("all");
    setFormKinds([]);
  };

  return (
    <>
      <TopHeader />

      <section className="space-y-3">
        <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
          <p className="text-lg font-semibold text-white">Покедекс</p>
          <p className="mt-1 text-sm text-slate-400">
            Полный список базовых и альтернативных форм с отметкой, что уже собрано.
          </p>

          <div className="mt-4 flex gap-2">
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Поиск по имени/id"
              className="min-w-0 flex-1 rounded-2xl border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-400"
            />
            <button
              type="button"
              onClick={() => setFiltersOpen((current) => !current)}
              className="rounded-2xl border border-slate-700 bg-slate-950 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-slate-500 hover:bg-slate-800"
            >
              ⚙️ Фильтры{activeFilterCount > 0 ? ` · ${activeFilterCount}` : ""}
            </button>
          </div>

          {activeFilterCount > 0 ? (
            <button
              type="button"
              onClick={resetFilters}
              className="mt-3 rounded-2xl border border-slate-800 px-3 py-2 text-sm text-slate-300 transition hover:border-slate-600 hover:text-white"
            >
              Сбросить
            </button>
          ) : null}
        </div>

        {filtersOpen ? (
          <section className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Редкость
              </p>
              <div className="flex flex-wrap gap-2">
                {RARITY_OPTIONS.map((rarity) => {
                  const selected = rarities.includes(rarity);
                  return (
                    <button
                      key={rarity}
                      type="button"
                      onClick={() => toggleRarity(rarity)}
                      className={`rounded-full border px-3 py-1.5 text-sm transition ${
                        selected
                          ? "border-cyan-400 bg-cyan-400/15 text-cyan-200"
                          : "border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white"
                      }`}
                    >
                      {rarity}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Стихии
                </p>
                <p className="text-xs text-slate-500">Можно выбрать до двух</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {TYPE_OPTIONS.map((pokemonType) => {
                  const selected = types.includes(pokemonType);
                  const disabled = !selected && types.length >= 2;
                  return (
                    <button
                      key={pokemonType}
                      type="button"
                      onClick={() => toggleType(pokemonType)}
                      disabled={disabled}
                      className={`rounded-full border px-3 py-1.5 text-sm capitalize transition ${
                        selected
                          ? "border-emerald-400 bg-emerald-400/15 text-emerald-200"
                          : "border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                      }`}
                    >
                      {pokemonType}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Собрано
              </p>
              <div className="flex flex-wrap gap-2">
                {[
                  { key: "all", label: "Все" },
                  { key: "collected", label: "Собранные" },
                  { key: "missing", label: "Не собранные" },
                ].map((option) => {
                  const selected = collectedState === option.key;
                  return (
                    <button
                      key={option.key}
                      type="button"
                      onClick={() => setCollectedState(option.key as "all" | "collected" | "missing")}
                      className={`rounded-full border px-3 py-1.5 text-sm transition ${
                        selected
                          ? "border-amber-400 bg-amber-400/15 text-amber-200"
                          : "border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Формы
              </p>
              <div className="flex flex-wrap gap-2">
                {FORM_KIND_OPTIONS.map((option) => {
                  const selected = formKinds.includes(option.key);
                  return (
                    <button
                      key={option.key}
                      type="button"
                      onClick={() => toggleFormKind(option.key)}
                      className={`rounded-full border px-3 py-1.5 text-sm transition ${
                        selected
                          ? "border-fuchsia-400 bg-fuchsia-400/15 text-fuchsia-200"
                          : "border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white"
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </section>
        ) : null}
      </section>

      {isLoading ? (
        <PokemonListSkeleton />
      ) : isError ? (
        <ErrorState
          icon="📘"
          title="Не удалось загрузить покедекс"
          description="Попробуй обновить страницу чуть позже."
        />
      ) : entries.length === 0 ? (
        <EmptyState
          icon="📘"
          title="Ничего не найдено"
          description="Попробуй изменить поиск или фильтры."
        />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {entries.map((entry) => (
            <Link key={entry.id} href={`/pokedex/pokemon?id=${entry.id}`} scroll={false} className="block">
              <PokemonCard
                pokemonId={entry.id}
                dexFormCode={entry.dexFormCode}
                name={entry.name}
                type={entry.type}
                rarity={normalizePokemonRarity(entry.rarity)}
                formBadge={entry.formBadge}
                imageUrl={entry.imageUrl}
                stateBadgeLabel={entry.isCollected ? "Есть" : "Нет"}
                dimmed={!entry.isCollected}
              />
            </Link>
          ))}
          <div ref={sentinelRef} className="col-span-2 h-1" />
          {isFetchingNextPage ? <PokemonListSkeleton /> : null}
        </div>
      )}
    </>
  );
}
