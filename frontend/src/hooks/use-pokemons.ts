import { useInfiniteQuery } from "@tanstack/react-query";

import { getPokemonsPage } from "@/lib/api";
import { useMiniAppDataReady } from "@/lib/telegram";

type UsePokemonsOptions = {
  lockedOnly?: boolean;
  rarities?: string[];
  types?: string[];
  duplicatesOnly?: boolean;
  query?: string;
};

export function usePokemons({
  lockedOnly = false,
  rarities = [],
  types = [],
  duplicatesOnly = false,
  query = "",
}: UsePokemonsOptions = {}) {
  const isReady = useMiniAppDataReady();

  const pokemonQuery = useInfiniteQuery({
    queryKey: ["pokemons", isReady ? "live" : "waiting", { lockedOnly, rarities, types, duplicatesOnly, query }],
    initialPageParam: 1,
    enabled: isReady,
    queryFn: ({ pageParam }) =>
      getPokemonsPage({
        pageParam,
        lockedOnly,
        rarities,
        types,
        duplicatesOnly,
        query,
      }),
    getNextPageParam: (lastPage) => lastPage.pageInfo.nextPage ?? undefined,
  });

  return {
    ...pokemonQuery,
    isLoading: pokemonQuery.isLoading || !isReady,
    entries: pokemonQuery.data?.pages.flatMap((page) => page.entries) ?? [],
    pageInfo: pokemonQuery.data?.pages.at(-1)?.pageInfo ?? null,
  };
}
