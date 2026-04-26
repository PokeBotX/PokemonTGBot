import { useQuery } from "@tanstack/react-query";

import { getTelegramAuthPreview } from "@/lib/api";
import { useMiniAppDataReady } from "@/lib/telegram";

export function useTelegramAuthPreview() {
  const isReady = useMiniAppDataReady();

  const query = useQuery({
    queryKey: ["telegram-auth-preview", isReady ? "live" : "waiting"],
    enabled: isReady,
    queryFn: getTelegramAuthPreview,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}
