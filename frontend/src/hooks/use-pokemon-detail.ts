import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cyclePokemonImage,
  getPokemonDetail,
  getPokemonInstances,
  getPokemonSellPrecheck,
  releasePokemon,
  sellPokemon,
  togglePokemonLock,
} from "@/lib/api";
import { useMiniAppDataReady } from "@/lib/telegram";

export function usePokemonDetail(userPokemonId: number | null) {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["pokemon-detail", isReady ? "live" : "waiting", userPokemonId],
    queryFn: () => getPokemonDetail(userPokemonId as number),
    enabled: isReady && userPokemonId !== null,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}

export function usePokemonInstances(userPokemonId: number | null) {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["pokemon-instances", isReady ? "live" : "waiting", userPokemonId],
    queryFn: () => getPokemonInstances(userPokemonId as number),
    enabled: isReady && userPokemonId !== null,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}

export function usePokemonLockToggle(userPokemonId: number | null) {
  const queryClient = useQueryClient();
  const isReady = useMiniAppDataReady();

  return useMutation({
    mutationFn: () => togglePokemonLock(userPokemonId as number),
    onSuccess: (data) => {
      queryClient.setQueryData(["pokemon-detail", isReady ? "live" : "waiting", userPokemonId], data);
      void queryClient.invalidateQueries({ queryKey: ["pokemons"] });
    },
  });
}

export function usePokemonImageCycle(userPokemonId: number | null) {
  const queryClient = useQueryClient();
  const isReady = useMiniAppDataReady();

  return useMutation({
    mutationFn: () => cyclePokemonImage(userPokemonId as number),
    onSuccess: (data) => {
      queryClient.setQueryData(["pokemon-detail", isReady ? "live" : "waiting", userPokemonId], data);
    },
  });
}

export function usePokemonRelease(userPokemonId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => releasePokemon(userPokemonId as number),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["pokemons"] });
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
      await queryClient.invalidateQueries({ queryKey: ["pokemon-detail"] });
    },
  });
}

export function usePokemonSell(userPokemonId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (price: number) => sellPokemon(userPokemonId as number, price),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["pokemons"] });
      await queryClient.invalidateQueries({ queryKey: ["market"] });
      await queryClient.invalidateQueries({ queryKey: ["pokemon-detail"] });
    },
  });
}

export function usePokemonSellPrecheck(userPokemonId: number | null) {
  return useMutation({
    mutationFn: () => getPokemonSellPrecheck(userPokemonId as number),
  });
}
