import { useQuery } from "@tanstack/react-query";

import { getMarketDetail } from "@/lib/api";
import { useMiniAppDataReady } from "@/lib/telegram";

export function useMarketDetail(listingId: number | null) {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["market-detail", isReady ? "live" : "waiting", listingId],
    queryFn: () => getMarketDetail(listingId as number),
    enabled: isReady && listingId !== null,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}
