"use client";

import {
  getTelegramInitData,
  getTelegramUser,
  isTelegramWebApp,
} from "@/lib/telegram";

import { ErrorState } from "@/components/error-state";
import { SectionCard } from "@/components/section-card";
import { InfoRow } from "@/components/info-row";
import { Skeleton } from "@/components/ui/skeleton";
import { useTelegramAuthPreview } from "@/hooks/use-telegram-auth-preview";

export function TelegramDebugCard() {
  const isTelegram = isTelegramWebApp();
  const user = getTelegramUser();
  const initData = getTelegramInitData();

  const { data, isLoading, isError } = useTelegramAuthPreview();

  return (
    <SectionCard title="Telegram Debug">
      <div className="flex flex-col gap-3">
        <InfoRow label="Telegram WebApp" value={isTelegram ? "yes" : "no"} />
        <InfoRow label="User найден" value={user ? "yes" : "no"} />
        <InfoRow label="initData есть" value={initData ? "yes" : "no"} />

        {isLoading ? (
          <Skeleton className="h-16 w-full rounded-2xl" />
        ) : isError || !data ? (
          <ErrorState
            icon="⚠️"
            title="Не удалось проверить Telegram auth"
            description="Пока не получилось получить состояние auth preview."
          />
        ) : (
          <div className="rounded-2xl bg-slate-800/70 p-4">
            <p className="text-sm text-slate-400">Auth preview</p>
            <p className="mt-2 text-sm text-white">{data.message}</p>
          </div>
        )}
      </div>
    </SectionCard>
  );
}
