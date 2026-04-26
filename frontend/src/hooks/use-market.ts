import { useInfiniteQuery } from "@tanstack/react-query";

import { getMarketPage } from "@/lib/api";

export function useMarket() {
  const isClient = typeof window !== "undefined";

  const query = useInfiniteQuery({
    queryKey: ["market"],
    initialPageParam: 1,
    enabled: isClient,
    queryFn: ({ pageParam }) => getMarketPage(pageParam),
    getNextPageParam: (lastPage) => lastPage.pageInfo.nextPage ?? undefined,
  });

  return {
    ...query,
    entries: query.data?.pages.flatMap((page) => page.entries) ?? [],
    pageInfo: query.data?.pages.at(-1)?.pageInfo ?? null,
  };
}
