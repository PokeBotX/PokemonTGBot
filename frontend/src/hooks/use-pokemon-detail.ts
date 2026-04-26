import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { cyclePokemonImage, getPokemonDetail, togglePokemonLock } from "@/lib/api";

export function usePokemonDetail(userPokemonId: number | null) {
  const isClient = typeof window !== "undefined";

  return useQuery({
    queryKey: ["pokemon-detail", userPokemonId],
    queryFn: () => getPokemonDetail(userPokemonId as number),
    enabled: isClient && userPokemonId !== null,
  });
}

export function usePokemonLockToggle(userPokemonId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => togglePokemonLock(userPokemonId as number),
    onSuccess: (data) => {
      queryClient.setQueryData(["pokemon-detail", userPokemonId], data);
      void queryClient.invalidateQueries({ queryKey: ["pokemons"] });
    },
  });
}

export function usePokemonImageCycle(userPokemonId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => cyclePokemonImage(userPokemonId as number),
    onSuccess: (data) => {
      queryClient.setQueryData(["pokemon-detail", userPokemonId], data);
    },
  });
}
