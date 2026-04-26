import { useQuery } from "@tanstack/react-query";

import { getProfile } from "@/lib/api";

export function useProfile() {
  const isClient = typeof window !== "undefined";

  return useQuery({
    queryKey: ["profile"],
    enabled: isClient,
    queryFn: getProfile,
  });
}
