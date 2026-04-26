import { useQuery } from "@tanstack/react-query";

import { getTelegramAuthPreview } from "@/lib/api";

export function useTelegramAuthPreview() {
  const isClient = typeof window !== "undefined";

  return useQuery({
    queryKey: ["telegram-auth-preview"],
    enabled: isClient,
    queryFn: getTelegramAuthPreview,
  });
}
