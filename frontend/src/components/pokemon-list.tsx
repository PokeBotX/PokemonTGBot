"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { PokemonCard } from "@/components/pokemon-card";
import { PokemonListSkeleton } from "@/components/pokemon-list-skeleton";
import { normalizePokemonRarity } from "@/components/pokemon-rarity";
import { usePokemons } from "@/hooks/use-pokemons";

type PokemonListProps = {
  lockedOnly?: boolean;
  rarities?: string[];
  types?: string[];
  duplicatesOnly?: boolean;
};

export function PokemonList({
  lockedOnly = false,
  rarities = [],
  types = [],
  duplicatesOnly = false,
}: PokemonListProps) {
  const pathname = usePathname();
  const {
    entries,
    isLoading,
    isError,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  } = usePokemons({ lockedOnly, rarities, types, duplicatesOnly });
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const restoreKey = `scroll:${pathname}:${lockedOnly}:${duplicatesOnly}:${rarities.join(",")}:${types.join(",")}`;

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
      (entries) => {
        const [entry] = entries;
        if (entry?.isIntersecting) {
          void fetchNextPage();
        }
      },
      { rootMargin: "240px 0px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [fetchNextPage, hasNextPage]);

  if (isLoading) {
    return <PokemonListSkeleton />;
  }

  if (isError) {
    return (
      <ErrorState
        icon="⚠️"
        title="Не удалось загрузить покемонов"
        description="Попробуй обновить страницу чуть позже."
      />
    );
  }
  const visiblePokemons = entries;

  if (visiblePokemons.length === 0) {
    return (
      <EmptyState
        icon={lockedOnly ? "🔒" : "📦"}
        title={lockedOnly ? "Залоченных покемонов пока нет" : "Покемонов пока нет"}
        description={
          lockedOnly
            ? "Когда ты залочишь покемона в боте, он появится здесь."
            : "Когда ты поймаешь первого покемона, он появится здесь."
        }
      />
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      {visiblePokemons.map((pokemon) => (
        <Link
          key={pokemon.userPokemonId ?? pokemon.id}
          href={`/pokemon?id=${pokemon.userPokemonId ?? pokemon.id}`}
          scroll={false}
          className="block"
        >
          <PokemonCard
            pokemonId={pokemon.id}
            name={pokemon.name}
            type={pokemon.type}
            rarity={normalizePokemonRarity(pokemon.rarity)}
            imageUrl={pokemon.imageUrl}
          />
        </Link>
      ))}
      <div ref={sentinelRef} className="col-span-2 h-1" />
      {isFetchingNextPage ? <PokemonListSkeleton /> : null}
    </div>
  );
}
