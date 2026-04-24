import { getTelegramInitData } from "@/lib/telegram";

type MiniAppProfile = {
  id: number;
  telegramId: number;
  name: string;
  username: string;
  pokemonCount: number;
  coins: number;
  language: string;
  completionPercent: number;
  totalCatalog: number;
  coverPokemonName: string | null;
  rarityProgress: Array<{
    rarity: string;
    ownedUnique: number;
    totalCatalog: number;
    percent: number;
  }>;
};

type MiniAppCollectionResponse = {
  entries: Array<{
    id: number;
    userPokemonId: number | null;
    name: string;
    type: string;
    level: number;
    rarity: string;
    quantity: number;
    baseHp: number;
    baseAttack: number;
    baseDefense: number;
    baseStamina: number;
    imageCreditId: number | null;
    isLocked: boolean;
  }>;
  pagination: {
    totalEntries: number;
    currentPage: number;
    totalPages: number;
  };
};

type TelegramAuthPreview = {
  authenticated: boolean;
  authDate: number;
  message?: string;
  telegramUser: {
    id: number;
    username?: string;
    first_name?: string;
    last_name?: string;
  };
  profile: MiniAppProfile | null;
};

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || ""
).replace(/\/$/, "");

function buildApiUrl(path: string) {
  if (!API_BASE_URL) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

function getAuthHeaders(): Record<string, string> {
  const initData = getTelegramInitData();
  if (!initData) {
    return {};
  }
  return { "X-Telegram-Init-Data": initData };
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // Keep the fallback detail for non-JSON error responses.
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

function getMockProfile(): MiniAppProfile {
  return {
    id: 1,
    telegramId: 0,
    name: "Dev Trainer",
    username: "local_dev",
    pokemonCount: 3,
    coins: 1250,
    language: "ru",
    completionPercent: 0.3,
    totalCatalog: 1025,
    coverPokemonName: "Pikachu",
    rarityProgress: [
      { rarity: "Common", ownedUnique: 2, totalCatalog: 500, percent: 0.4 },
      { rarity: "Rare", ownedUnique: 1, totalCatalog: 300, percent: 0.33 },
    ],
  };
}

function getMockCollection(): MiniAppCollectionResponse {
  return {
    entries: [
      {
        id: 25,
        userPokemonId: 1001,
        name: "Pikachu",
        type: "Electric",
        level: 1,
        rarity: "Rare",
        quantity: 1,
        baseHp: 35,
        baseAttack: 55,
        baseDefense: 40,
        baseStamina: 90,
        imageCreditId: null,
        isLocked: false,
      },
      {
        id: 1,
        userPokemonId: 1002,
        name: "Bulbasaur",
        type: "Grass",
        level: 1,
        rarity: "Common",
        quantity: 2,
        baseHp: 45,
        baseAttack: 49,
        baseDefense: 49,
        baseStamina: 100,
        imageCreditId: null,
        isLocked: false,
      },
    ],
    pagination: {
      totalEntries: 2,
      currentPage: 1,
      totalPages: 1,
    },
  };
}

export async function getProfile(): Promise<MiniAppProfile> {
  const initData = getTelegramInitData();
  if (!initData) {
    return getMockProfile();
  }

  const response = await fetch(buildApiUrl("/api/me"), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppProfile>(response);
}

export async function getPokemons(): Promise<MiniAppCollectionResponse["entries"]> {
  const initData = getTelegramInitData();
  if (!initData) {
    return getMockCollection().entries;
  }

  const response = await fetch(buildApiUrl("/api/collection"), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  const payload = await parseJsonResponse<MiniAppCollectionResponse>(response);
  return payload.entries;
}

export async function getTelegramAuthPreview(): Promise<TelegramAuthPreview> {
  const initData = getTelegramInitData();
  if (!initData) {
    return {
      authenticated: false,
      authDate: 0,
      message: "Локальный preview без Telegram initData",
      telegramUser: {
        id: 0,
        username: "local_dev",
        first_name: "Dev",
        last_name: "User",
      },
      profile: getMockProfile(),
    };
  }

  const response = await fetch(buildApiUrl("/auth/telegram"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ initData }),
    cache: "no-store",
  });
  return parseJsonResponse<TelegramAuthPreview>(response);
}
