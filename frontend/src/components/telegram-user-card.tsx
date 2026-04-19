"use client";

import { useEffect, useState } from "react";

import { getTelegramUser, getTelegramWebApp } from "@/lib/telegram";

type TelegramUserView = {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
};

export function TelegramUserCard() {
  const [user, setUser] = useState<TelegramUserView | null>(null);

  useEffect(() => {
    const webApp = getTelegramWebApp();

    webApp?.ready();
    webApp?.expand();

    setUser(getTelegramUser());
  }, []);

  const displayName = user
    ? [user.first_name, user.last_name].filter(Boolean).join(" ") ||
      user.username ||
      `User ${user.id}`
    : "Dev User";

  return (
    <div className="rounded-3xl border border-yellow-400/30 bg-yellow-400/10 p-5">
      <p className="text-sm text-yellow-200">Telegram пользователь</p>
      <h2 className="mt-2 text-xl font-semibold">{displayName}</h2>

      {user?.username ? (
        <p className="mt-1 text-sm text-yellow-100">@{user.username}</p>
      ) : (
        <p className="mt-1 text-sm text-yellow-100">
          Открыто вне Telegram или пользователь пока не найден
        </p>
      )}
    </div>
  );
}
