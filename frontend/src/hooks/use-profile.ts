import { useQuery } from "@tanstack/react-query";

import { getProfile } from "@/lib/api";
import { useMiniAppDataReady } from "@/lib/telegram";

export function useProfile() {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["profile", isReady ? "live" : "waiting"],
    enabled: isReady,
    queryFn: getProfile,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}
