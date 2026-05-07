import { useQuery } from "@tanstack/react-query";

import { getMarketPage, getMyMarketListings, getMyMarketRequests } from "@/lib/api";
import { useMiniAppDataReady } from "@/lib/telegram";

export function useMyMarketListings() {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["market-my-listings", isReady ? "live" : "waiting"],
    queryFn: () => getMyMarketListings(),
    enabled: isReady,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}

export function useMyMarketRequests() {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["market-my-requests", isReady ? "live" : "waiting"],
    queryFn: () => getMyMarketRequests(),
    enabled: isReady,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}

export function useMarketBalance() {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["market-balance", isReady ? "live" : "waiting"],
    queryFn: () => getMarketPage(1),
    enabled: isReady,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
    pokecoinBalance: query.data?.pokecoinBalance ?? 0,
  };
}
