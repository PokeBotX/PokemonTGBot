"use client";

import { useMemo, useState } from "react";

import { PokemonList } from "@/components/pokemon-list";
import { TopHeader } from "@/components/top-header";

const COLLECTION_RARITY_OPTIONS = ["Legendary", "Epic", "Rare", "Common"] as const;
const COLLECTION_TYPE_OPTIONS = [
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

type CollectionScreenProps = {
  showTopHeader?: boolean;
};

export function CollectionScreen({ showTopHeader = true }: CollectionScreenProps) {
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [rarities, setRarities] = useState<string[]>([]);
  const [types, setTypes] = useState<string[]>([]);
  const [duplicatesOnly, setDuplicatesOnly] = useState(false);

  const activeFilterCount = useMemo(
    () => rarities.length + types.length + (duplicatesOnly ? 1 : 0),
    [duplicatesOnly, rarities.length, types.length],
  );

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

  const resetFilters = () => {
    setRarities([]);
    setTypes([]);
    setDuplicatesOnly(false);
  };

  return (
    <>
      {showTopHeader ? <TopHeader /> : null}
      <section className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setFiltersOpen((current) => !current)}
            className="rounded-2xl border border-slate-700 bg-slate-950 px-4 py-2 text-sm font-medium text-slate-100 transition hover:border-slate-500 hover:bg-slate-800"
          >
            ⚙️ Фильтры{activeFilterCount > 0 ? ` · ${activeFilterCount}` : ""}
          </button>
          {activeFilterCount > 0 ? (
            <button
              type="button"
              onClick={resetFilters}
              className="rounded-2xl border border-slate-800 px-3 py-2 text-sm text-slate-300 transition hover:border-slate-600 hover:text-white"
            >
              Сбросить
            </button>
          ) : null}
      </section>

      {filtersOpen ? (
        <section className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Редкость
            </p>
            <div className="flex flex-wrap gap-2">
              {COLLECTION_RARITY_OPTIONS.map((rarity) => {
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
              {COLLECTION_TYPE_OPTIONS.map((pokemonType) => {
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

          <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-900/70 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-slate-100">Только дубликаты</p>
              <p className="text-xs text-slate-400">
                Показывать только виды, у которых есть больше одного экземпляра.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setDuplicatesOnly((current) => !current)}
              className={`rounded-full border px-3 py-1.5 text-sm transition ${
                duplicatesOnly
                  ? "border-violet-400 bg-violet-400/15 text-violet-200"
                  : "border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white"
              }`}
            >
              {duplicatesOnly ? "Вкл" : "Выкл"}
            </button>
          </div>
        </section>
      ) : null}

      <PokemonList
        rarities={rarities}
        types={types}
        duplicatesOnly={duplicatesOnly}
      />
    </>
  );
}
