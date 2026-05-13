"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PokemonCard } from "@/components/pokemon-card";
import { PokemonListSkeleton } from "@/components/pokemon-list-skeleton";
import { normalizePokemonRarity } from "@/components/pokemon-rarity";
import { useMarket } from "@/hooks/use-market";

type MarketListProps = {
  query?: string;
};

export function MarketList({ query = "" }: MarketListProps) {
  const {
    entries,
    isLoading,
    isError,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  } = useMarket(query);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !hasNextPage) {
      return;
    }

    const observer = new IntersectionObserver(
      (items) => {
        const [entry] = items;
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
        icon="🛒"
        title="Не удалось загрузить рынок"
        description="Попробуй обновить страницу чуть позже."
      />
    );
  }

  if (entries.length === 0) {
    return (
      <EmptyState
        icon="🪙"
        title="На рынке пока нет активных лотов"
        description="Когда пользователи выставят покемонов, они появятся здесь."
      />
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      {entries.map((entry) => (
        <Link key={entry.listingId} href={`/shop/listing?id=${entry.listingId}`} className="block">
            <PokemonCard
              pokemonId={entry.pokemonId}
              dexFormCode={entry.dexFormCode}
              name={entry.name}
            type={entry.type}
            rarity={normalizePokemonRarity(entry.rarity)}
            formBadge={entry.formBadge}
            imageUrl={entry.imageUrl}
            priceLabel={`🪙 ${entry.price}`}
          />
        </Link>
      ))}
      <div ref={sentinelRef} className="col-span-2 h-1" />
      {isFetchingNextPage ? <PokemonListSkeleton /> : null}
    </div>
  );
}
