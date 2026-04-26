import { useInfiniteQuery } from "@tanstack/react-query";

import { getPokemonsPage } from "@/lib/api";

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
  const query = useInfiniteQuery({
    queryKey: ["pokemons", { lockedOnly, rarities, types, duplicatesOnly }],
    initialPageParam: 1,
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
    entries: query.data?.pages.flatMap((page) => page.entries) ?? [],
    pageInfo: query.data?.pages.at(-1)?.pageInfo ?? null,
  };
}
