"use client";

import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { PokemonCard } from "@/components/pokemon-card";
import { PokemonListSkeleton } from "@/components/pokemon-list-skeleton";
import { usePokemons } from "@/hooks/use-pokemons";

export function PokemonList() {
  const { data, isLoading, isError } = usePokemons();

  if (isLoading) {
    return <PokemonListSkeleton />;
  }

  if (isError || !data) {
    return (
      <ErrorState
        icon="⚠️"
        title="Не удалось загрузить покемонов"
        description="Попробуй обновить страницу чуть позже."
      />
    );
  }

  if (data.length === 0) {
    return (
      <EmptyState
        icon="📦"
        title="Покемонов пока нет"
        description="Когда ты поймаешь первого покемона, он появится здесь."
      />
    );
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
