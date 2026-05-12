import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createPokedexBuyRequest,
  getPokedexBuyRequestPrecheck,
  getPokedexDetail,
  getPokedexPage,
} from "@/lib/api";
import { useMiniAppDataReady } from "@/lib/telegram";

type UsePokedexOptions = {
  rarities?: string[];
  types?: string[];
  collectedState?: "all" | "collected" | "missing";
  formKinds?: string[];
  query?: string;
};

export function usePokedex({
  rarities = [],
  types = [],
  collectedState = "all",
  formKinds = [],
  query = "",
}: UsePokedexOptions = {}) {
  const isReady = useMiniAppDataReady();

  const pagedQuery = useInfiniteQuery({
    queryKey: [
      "pokedex",
      isReady ? "live" : "waiting",
      { rarities, types, collectedState, formKinds, query },
    ],
    initialPageParam: 1,
    enabled: isReady,
    queryFn: ({ pageParam }) =>
      getPokedexPage({
        pageParam,
        rarities,
        types,
        collectedState,
        formKinds,
        query,
      }),
    getNextPageParam: (lastPage) => lastPage.pageInfo.nextPage ?? undefined,
  });

  return {
    ...pagedQuery,
    isLoading: pagedQuery.isLoading || !isReady,
    entries: pagedQuery.data?.pages.flatMap((page) => page.entries) ?? [],
    pageInfo: pagedQuery.data?.pages.at(-1)?.pageInfo ?? null,
  };
}

export function usePokedexDetail(pokemonId: number | null) {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["pokedex-detail", isReady ? "live" : "waiting", pokemonId],
    queryFn: () => getPokedexDetail(pokemonId as number),
    enabled: isReady && pokemonId !== null,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}

export function usePokedexBuyRequestPrecheck(pokemonId: number | null) {
  return useMutation({
    mutationFn: () => getPokedexBuyRequestPrecheck(pokemonId as number),
  });
}

export function usePokedexBuyRequestCreate(pokemonId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (price: number) => createPokedexBuyRequest(pokemonId as number, price),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["market-my-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["market"] });
      await queryClient.invalidateQueries({ queryKey: ["pokedex-detail"] });
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}
