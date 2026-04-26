"use client";

import { useSyncExternalStore } from "react";

type TelegramUser = {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  language_code?: string;
};

type TelegramWebApp = {
  initData: string;
  initDataUnsafe?: {
    user?: TelegramUser;
  };
  ready: () => void;
  expand: () => void;
};

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}

const DEV_TELEGRAM_USER: TelegramUser = {
  id: Number(process.env.NEXT_PUBLIC_DEV_TELEGRAM_ID ?? "1640978922"),
  first_name: process.env.NEXT_PUBLIC_DEV_FIRST_NAME?.trim() || "Artem",
  last_name: process.env.NEXT_PUBLIC_DEV_LAST_NAME?.trim() || "",
  username: process.env.NEXT_PUBLIC_DEV_USERNAME?.trim() || "termenater",
  language_code: "ru",
};

export function getTelegramWebApp() {
  if (typeof window === "undefined") {
    return null;
  }

  return window.Telegram?.WebApp ?? null;
}

export function getTelegramUser() {
  const webApp = getTelegramWebApp();
  return webApp?.initDataUnsafe?.user ?? DEV_TELEGRAM_USER;
}

export function getTelegramInitData() {
  const webApp = getTelegramWebApp();
  return webApp?.initData ?? "";
}

export function isTelegramWebApp() {
  return getTelegramWebApp() !== null;
}

type TelegramSnapshot = {
  isTelegram: boolean;
  user: TelegramUser | null;
  initData: string;
};

const EMPTY_TELEGRAM_SNAPSHOT: TelegramSnapshot = {
  isTelegram: false,
  user: DEV_TELEGRAM_USER,
  initData: "",
};

function subscribeTelegramSnapshot() {
  return () => {};
}

function getTelegramSnapshot(): TelegramSnapshot {
  const webApp = getTelegramWebApp();
  if (!webApp) {
    return EMPTY_TELEGRAM_SNAPSHOT;
  }

  return {
    isTelegram: true,
    user: webApp.initDataUnsafe?.user ?? null,
    initData: webApp.initData ?? "",
  };
}

export function useTelegramSnapshot() {
  return useSyncExternalStore(
    subscribeTelegramSnapshot,
    getTelegramSnapshot,
    () => EMPTY_TELEGRAM_SNAPSHOT,
  );
}

export function getDevelopmentTelegramUser() {
  return DEV_TELEGRAM_USER;
}
