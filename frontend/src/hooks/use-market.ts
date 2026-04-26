import { useInfiniteQuery } from "@tanstack/react-query";

import { getMarketPage } from "@/lib/api";

export function useMarket() {
  const query = useInfiniteQuery({
    queryKey: ["market"],
    initialPageParam: 1,
    queryFn: ({ pageParam }) => getMarketPage(pageParam),
    getNextPageParam: (lastPage) => lastPage.pageInfo.nextPage ?? undefined,
  });

  return {
    ...query,
    entries: query.data?.pages.flatMap((page) => page.entries) ?? [],
    pageInfo: query.data?.pages.at(-1)?.pageInfo ?? null,
  };
}
