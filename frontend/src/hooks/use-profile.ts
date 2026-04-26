import { useQuery } from "@tanstack/react-query";

import { getProfile } from "@/lib/api";
import { useMiniAppDataReady, useMiniAppQueryScope } from "@/lib/telegram";

export function useProfile() {
  const isReady = useMiniAppDataReady();
  const queryScope = useMiniAppQueryScope();

  const query = useQuery({
    queryKey: ["profile", queryScope],
    enabled: isReady,
    queryFn: getProfile,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}
