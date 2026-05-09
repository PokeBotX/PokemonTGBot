import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  buyMarketListing,
  cancelMarketRequest,
  getMarketDetail,
  getMyMarketListingDetail,
  getMyMarketRequestDetail,
  removeMarketListing,
} from "@/lib/api";
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

export function useMyMarketListingDetail(listingId: number | null) {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["market-my-listing-detail", isReady ? "live" : "waiting", listingId],
    queryFn: () => getMyMarketListingDetail(listingId as number),
    enabled: isReady && listingId !== null,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}

export function useMyMarketRequestDetail(requestId: number | null) {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["market-my-request-detail", isReady ? "live" : "waiting", requestId],
    queryFn: () => getMyMarketRequestDetail(requestId as number),
    enabled: isReady && requestId !== null,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}

export function useMarketListingPurchase(listingId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => buyMarketListing(listingId as number),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["market"] });
      await queryClient.invalidateQueries({ queryKey: ["market-detail"] });
      await queryClient.invalidateQueries({ queryKey: ["market-my-listings"] });
      await queryClient.invalidateQueries({ queryKey: ["market-my-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["pokemons"] });
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
      await queryClient.invalidateQueries({ queryKey: ["pokemon-detail"] });
    },
  });
}

export function useMarketListingRemove(listingId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => removeMarketListing(listingId as number),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["market"] });
      await queryClient.invalidateQueries({ queryKey: ["market-my-listings"] });
      await queryClient.invalidateQueries({ queryKey: ["market-my-listing-detail"] });
      await queryClient.invalidateQueries({ queryKey: ["pokemons"] });
      await queryClient.invalidateQueries({ queryKey: ["pokemon-detail"] });
    },
  });
}

export function useMarketRequestCancel(requestId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => cancelMarketRequest(requestId as number),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["market-my-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["market-my-request-detail"] });
      await queryClient.invalidateQueries({ queryKey: ["market"] });
    },
  });
}
