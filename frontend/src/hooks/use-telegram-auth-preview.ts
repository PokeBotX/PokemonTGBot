import { useQuery } from "@tanstack/react-query";

import { getTelegramAuthPreview } from "@/lib/api";
import { useMiniAppDataReady, useMiniAppQueryScope } from "@/lib/telegram";

export function useTelegramAuthPreview() {
  const isReady = useMiniAppDataReady();
  const queryScope = useMiniAppQueryScope();

  const query = useQuery({
    queryKey: ["telegram-auth-preview", queryScope],
    enabled: isReady,
    queryFn: getTelegramAuthPreview,
  });

  return {
    ...query,
    isLoading: query.isLoading || !isReady,
  };
}
