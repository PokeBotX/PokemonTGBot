import { useQuery } from "@tanstack/react-query";

import { getPokemons } from "@/lib/api";

export function usePokemons() {
  return useQuery({
    queryKey: ["pokemons"],
    queryFn: getPokemons,
  });
}
