import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { cyclePokemonImage, getPokemonDetail, togglePokemonLock } from "@/lib/api";
import { useMiniAppDataReady, useMiniAppQueryScope } from "@/lib/telegram";

export function usePokemonDetail(userPokemonId: number | null) {
  const isReady = useMiniAppDataReady();
  const queryScope = useMiniAppQueryScope();

  const query = useQuery({
    queryKey: ["pokemon-detail", queryScope, userPokemonId],
    queryFn: () => getPokemonDetail(userPokemonId as number),
    enabled: isReady && userPokemonId !== null,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}

export function usePokemonLockToggle(userPokemonId: number | null) {
  const queryClient = useQueryClient();
  const queryScope = useMiniAppQueryScope();

  return useMutation({
    mutationFn: () => togglePokemonLock(userPokemonId as number),
    onSuccess: (data) => {
      queryClient.setQueryData(["pokemon-detail", queryScope, userPokemonId], data);
      void queryClient.invalidateQueries({ queryKey: ["pokemons"] });
    },
  });
}

export function usePokemonImageCycle(userPokemonId: number | null) {
  const queryClient = useQueryClient();
  const queryScope = useMiniAppQueryScope();

  return useMutation({
    mutationFn: () => cyclePokemonImage(userPokemonId as number),
    onSuccess: (data) => {
      queryClient.setQueryData(["pokemon-detail", queryScope, userPokemonId], data);
    },
  });
}
