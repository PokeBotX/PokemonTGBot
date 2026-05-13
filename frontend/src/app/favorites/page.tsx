"use client";

import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PokemonList } from "@/components/pokemon-list";
import { TopHeader } from "@/components/top-header";

export default function FavoritesPage() {
  const [query, setQuery] = useState("");

  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
      showScrollToTop
    >
      <TopHeader />
      <section className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Поиск по имени/id"
          className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-400"
        />

        {query.trim() ? (
          <button
            type="button"
            onClick={() => setQuery("")}
            className="mt-3 rounded-2xl border border-slate-800 px-3 py-2 text-sm text-slate-300 transition hover:border-slate-600 hover:text-white"
          >
            Сбросить
          </button>
        ) : null}
      </section>
      <PokemonList lockedOnly query={query} />
    </AppShell>
  );
}
