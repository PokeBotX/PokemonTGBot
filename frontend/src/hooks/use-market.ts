import { useInfiniteQuery } from "@tanstack/react-query";

import { getMarketPage } from "@/lib/api";
import { useMiniAppDataReady, useMiniAppQueryScope } from "@/lib/telegram";

export function useMarket() {
  const isReady = useMiniAppDataReady();
  const queryScope = useMiniAppQueryScope();

  const query = useInfiniteQuery({
    queryKey: ["market", queryScope],
    initialPageParam: 1,
    enabled: isReady,
    queryFn: ({ pageParam }) => getMarketPage(pageParam),
    getNextPageParam: (lastPage) => lastPage.pageInfo.nextPage ?? undefined,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
    entries: query.data?.pages.flatMap((page) => page.entries) ?? [],
    pageInfo: query.data?.pages.at(-1)?.pageInfo ?? null,
  };
}
