"use client";

import { PokemonCard } from "@/components/pokemon-card";
import { usePokemons } from "@/hooks/use-pokemons";

export function PokemonList() {
  const { data, isLoading, isError } = usePokemons();

  if (isLoading) {
    return <p className="text-slate-400">Загрузка покемонов...</p>;
  }

  if (isError || !data) {
    return <p className="text-red-300">Ошибка загрузки покемонов.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {data.map((pokemon) => (
        <PokemonCard
          key={pokemon.id}
          name={pokemon.name}
          type={pokemon.type}
          level={pokemon.level}
          rarity={pokemon.rarity}
        />
      ))}
    </div>
  );
}
