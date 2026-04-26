import { useInfiniteQuery } from "@tanstack/react-query";

import { getPokemonsPage } from "@/lib/api";
import { useMiniAppDataReady } from "@/lib/telegram";

type UsePokemonsOptions = {
  lockedOnly?: boolean;
  rarities?: string[];
  types?: string[];
  duplicatesOnly?: boolean;
};

export function usePokemons({
  lockedOnly = false,
  rarities = [],
  types = [],
  duplicatesOnly = false,
}: UsePokemonsOptions = {}) {
  const isReady = useMiniAppDataReady();

  const query = useInfiniteQuery({
    queryKey: ["pokemons", isReady ? "live" : "waiting", { lockedOnly, rarities, types, duplicatesOnly }],
    initialPageParam: 1,
    enabled: isReady,
    queryFn: ({ pageParam }) =>
      getPokemonsPage({
        pageParam,
        lockedOnly,
        rarities,
        types,
        duplicatesOnly,
      }),
    getNextPageParam: (lastPage) => lastPage.pageInfo.nextPage ?? undefined,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
    entries: query.data?.pages.flatMap((page) => page.entries) ?? [],
    pageInfo: query.data?.pages.at(-1)?.pageInfo ?? null,
  };
}
