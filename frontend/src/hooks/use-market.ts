import { useInfiniteQuery } from "@tanstack/react-query";

import { getMarketPage } from "@/lib/api";
import { useMiniAppDataReady } from "@/lib/telegram";

export function useMarket(query = "") {
  const isReady = useMiniAppDataReady();

  const marketQuery = useInfiniteQuery({
    queryKey: ["market", isReady ? "live" : "waiting", query],
    initialPageParam: 1,
    enabled: isReady,
    queryFn: ({ pageParam }) => getMarketPage(pageParam, query),
    getNextPageParam: (lastPage) => lastPage.pageInfo.nextPage ?? undefined,
  });

  return {
    ...marketQuery,
    isLoading: marketQuery.isLoading || !isReady,
    entries: marketQuery.data?.pages.flatMap((page) => page.entries) ?? [],
    pageInfo: marketQuery.data?.pages.at(-1)?.pageInfo ?? null,
    pokecoinBalance: marketQuery.data?.pages.at(0)?.pokecoinBalance ?? 0,
  };
}
