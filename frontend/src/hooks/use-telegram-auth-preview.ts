import { useQuery } from "@tanstack/react-query";

import { getTelegramAuthPreview } from "@/lib/api";

export function useTelegramAuthPreview() {
  return useQuery({
    queryKey: ["telegram-auth-preview"],
    queryFn: getTelegramAuthPreview,
  });
}
