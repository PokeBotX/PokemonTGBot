import {
  getDevelopmentTelegramUser,
  getTelegramInitData,
  isLocalMiniAppDevelopment,
} from "@/lib/telegram";

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
  baseDexCount: number;
  baseDexCatalog: number;
  baseDexCompletionPercent: number;
  totalFormCount: number;
  totalFormCatalog: number;
  totalFormCompletionPercent: number;
  accountAgeLabel: string;
  coverPokemonName: string | null;
  coverPokemonImageUrl: string | null;
  rarityProgress: Array<{
    rarity: string;
    ownedUnique: number;
    totalCatalog: number;
    percent: number;
  }>;
};

export type MiniAppCollectionEntry = {
  id: number;
  dexFormCode?: string | null;
  userPokemonId: number | null;
  name: string;
  type: string;
  level: number;
  rarity: string;
  formBadge?: string | null;
  quantity: number;
  baseHp: number;
  baseAttack: number;
  baseDefense: number;
  baseStamina: number;
  imageCreditId: number | null;
  imageUrl: string | null;
  isLocked: boolean;
};

export type MiniAppMarketEntry = {
  listingId: number;
  pokemonId: number;
  dexFormCode?: string | null;
  userPokemonId: number;
  name: string;
  type: string;
  rarity: string;
  formBadge?: string | null;
  price: number;
  sellerLabel: string;
  daysRemaining: number;
  imageCreditId: number | null;
  imageUrl: string | null;
};

export type MiniAppMarketRequestEntry = {
  requestId: number;
  pokemonId: number;
  dexFormCode?: string | null;
  name: string;
  type: string;
  rarity: string;
  formBadge?: string | null;
  price: number;
  reservedAmount: number;
  requesterLabel: string;
  imageCreditId: number | null;
  imageUrl: string | null;
};

export type MiniAppMarketDetail = {
  listingId: number;
  pokecoinBalance: number;
  userPokemonId: number;
  pokemonId: number;
  dexFormCode?: string | null;
  name: string;
  rarity: string;
  formBadge?: string | null;
  type: string;
  price: number;
  sellerLabel: string;
  daysRemaining: number;
  baseHp: number;
  baseAttack: number;
  baseDefense: number;
  baseStamina: number;
  imageCreditId: number | null;
  imageUrl: string | null;
  sourceUrl: string | null;
  imageVariant: {
    position: number;
    total: number;
    canSwitch: boolean;
  };
};

export type MiniAppMarketRequestDetail = {
  requestId: number;
  pokecoinBalance: number;
  pokemonId: number;
  dexFormCode?: string | null;
  name: string;
  rarity: string;
  formBadge?: string | null;
  type: string;
  price: number;
  reservedAmount: number;
  requesterLabel: string;
  baseHp: number;
  baseAttack: number;
  baseDefense: number;
  baseStamina: number;
  imageCreditId: number | null;
  imageUrl: string | null;
  sourceUrl: string | null;
  imageVariant: {
    position: number;
    total: number;
    canSwitch: boolean;
  };
};

export type MiniAppPokemonDetail = {
  id: number;
  dexFormCode?: string | null;
  userPokemonId: number;
  name: string;
  rarity: string;
  formBadge?: string | null;
  type: string;
  quantity: number;
  baseHp: number;
  baseAttack: number;
  baseDefense: number;
  baseStamina: number;
  isLocked: boolean;
  isInPvpTeam: boolean;
  releaseRewardAmount: number;
  imageCreditId: number | null;
  imageUrl: string | null;
  sourceUrl: string | null;
  imageVariant: {
    position: number;
    total: number;
    canSwitch: boolean;
  };
};

export type MiniAppPokemonInstanceEntry = {
  userPokemonId: number;
  pokemonId: number;
  dexFormCode?: string | null;
  name: string;
  rarity: string;
  type: string;
  formBadge?: string | null;
  isLocked: boolean;
  isInPvpTeam: boolean;
};

type MiniAppCollectionResponse = {
  entries: MiniAppCollectionEntry[];
  pageInfo: {
    totalEntries: number;
    currentPage: number;
    totalPages: number;
    pageSize: number;
    hasNext: boolean;
    hasPrevious: boolean;
    nextPage: number | null;
  };
  appliedFilters: {
    rarities: string[];
    types: string[];
    duplicatesOnly: boolean;
    lockedOnly: boolean;
  };
};

type MiniAppMarketResponse = {
  pokecoinBalance: number;
  entries: MiniAppMarketEntry[];
  pageInfo: {
    totalEntries: number;
    currentPage: number;
    totalPages: number;
    pageSize: number;
    hasNext: boolean;
    hasPrevious: boolean;
    nextPage: number | null;
  };
};

type MiniAppMyMarketListingsResponse = {
  pokecoinBalance: number;
  entries: MiniAppMarketEntry[];
};

type MiniAppMyMarketRequestsResponse = {
  pokecoinBalance: number;
  entries: MiniAppMarketRequestEntry[];
};

type MiniAppPokemonInstancesResponse = {
  entries: MiniAppPokemonInstanceEntry[];
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

const CONFIGURED_API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || ""
).replace(/\/$/, "");
const DEV_TELEGRAM_ID = process.env.NEXT_PUBLIC_DEV_TELEGRAM_ID?.trim() || "1640978922";

function getApiBaseUrl() {
  if (CONFIGURED_API_BASE_URL) {
    return CONFIGURED_API_BASE_URL;
  }

  if (typeof window === "undefined") {
    return "";
  }

  const hostname = window.location.hostname;
  if (hostname === "127.0.0.1" || hostname === "localhost") {
    return "http://127.0.0.1:8000";
  }

  return "";
}

function buildApiUrl(path: string) {
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) {
    return path;
  }
  return `${apiBaseUrl}${path}`;
}

function canUseLiveBackend() {
  return Boolean(getTelegramInitData() || isLocalMiniAppDevelopment());
}

function getAuthHeaders(): Record<string, string> {
  const initData = getTelegramInitData();
  if (initData) {
    return { "X-Telegram-Init-Data": initData };
  }
  if (!isLocalMiniAppDevelopment()) {
    return {};
  }
  return { "X-Dev-Telegram-Id": DEV_TELEGRAM_ID };
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
  const devUser = getDevelopmentTelegramUser();
  return {
    id: 1,
    telegramId: devUser.id,
    name: [devUser.first_name, devUser.last_name].filter(Boolean).join(" ") || devUser.username || "termenater",
    username: devUser.username || "termenater",
    pokemonCount: 3,
    coins: 1250,
    language: "ru",
    completionPercent: 16,
    totalCatalog: 1025,
    baseDexCount: 3,
    baseDexCatalog: 1025,
    baseDexCompletionPercent: 16,
    totalFormCount: 3,
    totalFormCatalog: 1025,
    totalFormCompletionPercent: 16,
    accountAgeLabel: "1 месяц",
    coverPokemonName: "Pikachu",
    coverPokemonImageUrl: null,
    rarityProgress: [
      { rarity: "Legendary", ownedUnique: 1, totalCatalog: 65, percent: 2 },
      { rarity: "Epic", ownedUnique: 0, totalCatalog: 154, percent: 0 },
      { rarity: "Rare", ownedUnique: 1, totalCatalog: 306, percent: 1 },
      { rarity: "Common", ownedUnique: 1, totalCatalog: 514, percent: 0 },
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
        formBadge: null,
        quantity: 1,
        baseHp: 35,
        baseAttack: 55,
        baseDefense: 40,
        baseStamina: 90,
        imageCreditId: null,
        imageUrl: null,
        isLocked: false,
      },
      {
        id: 1,
        userPokemonId: 1002,
        name: "Bulbasaur",
        type: "Grass",
        level: 1,
        rarity: "Common",
        formBadge: null,
        quantity: 2,
        baseHp: 45,
        baseAttack: 49,
        baseDefense: 49,
        baseStamina: 100,
        imageCreditId: null,
        imageUrl: null,
        isLocked: true,
      },
    ],
    pageInfo: {
      totalEntries: 2,
      currentPage: 1,
      totalPages: 1,
      pageSize: 24,
      hasNext: false,
      hasPrevious: false,
      nextPage: null,
    },
    appliedFilters: {
      rarities: [],
      types: [],
      duplicatesOnly: false,
      lockedOnly: false,
    }
  };
}

function getMockMarket(): MiniAppMarketResponse {
  return {
    pokecoinBalance: 880,
    entries: [
      {
        listingId: 1,
        pokemonId: 25,
        userPokemonId: 1001,
        name: "Pikachu",
        type: "Electric",
        rarity: "Rare",
        formBadge: null,
        price: 240,
        sellerLabel: "termenater",
        daysRemaining: 6,
        imageCreditId: null,
        imageUrl: null,
      },
      {
        listingId: 2,
        pokemonId: 6,
        userPokemonId: 1002,
        name: "Charizard",
        type: "Fire/Flying",
        rarity: "Epic",
        formBadge: null,
        price: 1200,
        sellerLabel: "termenater",
        daysRemaining: 5,
        imageCreditId: null,
        imageUrl: null,
      },
    ],
    pageInfo: {
      totalEntries: 2,
      currentPage: 1,
      totalPages: 1,
      pageSize: 20,
      hasNext: false,
      hasPrevious: false,
      nextPage: null,
    },
  };
}

function getMockMarketDetail(listingId: number): MiniAppMarketDetail {
  return {
    listingId,
    pokecoinBalance: 880,
    userPokemonId: 1001,
    pokemonId: 25,
    name: "Pikachu",
    rarity: "Rare",
    formBadge: null,
    type: "Electric",
    price: 240,
    sellerLabel: "termenater",
    daysRemaining: 6,
    baseHp: 35,
    baseAttack: 55,
    baseDefense: 40,
    baseStamina: 90,
    imageCreditId: null,
    imageUrl: null,
    sourceUrl: null,
    imageVariant: {
      position: 1,
      total: 1,
      canSwitch: false,
    },
  };
}

function getMockPokemonDetail(userPokemonId: number): MiniAppPokemonDetail {
  return {
    id: 25,
    userPokemonId,
    name: "Pikachu",
    rarity: "Rare",
    formBadge: null,
    type: "Electric",
    quantity: 1,
    baseHp: 35,
    baseAttack: 55,
    baseDefense: 40,
    baseStamina: 90,
    isLocked: false,
    isInPvpTeam: false,
    releaseRewardAmount: 25,
    imageCreditId: null,
    imageUrl: null,
    sourceUrl: null,
    imageVariant: {
      position: 1,
      total: 1,
      canSwitch: false,
    },
  };
}

function getMockMarketRequestDetail(requestId: number): MiniAppMarketRequestDetail {
  return {
    requestId,
    pokecoinBalance: 880,
    pokemonId: 25,
    dexFormCode: "25",
    name: "Pikachu",
    rarity: "Rare",
    formBadge: null,
    type: "Electric",
    price: 240,
    reservedAmount: 240,
    requesterLabel: "termenater",
    baseHp: 35,
    baseAttack: 55,
    baseDefense: 40,
    baseStamina: 90,
    imageCreditId: null,
    imageUrl: null,
    sourceUrl: null,
    imageVariant: {
      position: 1,
      total: 1,
      canSwitch: false,
    },
  };
}

export async function getProfile(): Promise<MiniAppProfile> {
  if (!canUseLiveBackend()) {
    return getMockProfile();
  }

  const response = await fetch(buildApiUrl("/api/me"), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppProfile>(response);
}

type GetPokemonsPageOptions = {
  pageParam?: number;
  lockedOnly?: boolean;
  rarities?: string[];
  types?: string[];
  duplicatesOnly?: boolean;
  pageSize?: number;
};

export async function getPokemonsPage({
  pageParam = 1,
  lockedOnly = false,
  rarities = [],
  types = [],
  duplicatesOnly = false,
  pageSize = 24,
}: GetPokemonsPageOptions = {}): Promise<MiniAppCollectionResponse> {
  if (!canUseLiveBackend()) {
    const mockCollection = getMockCollection();
    return {
      ...mockCollection,
      entries: lockedOnly
        ? mockCollection.entries.filter((entry) => entry.isLocked)
        : mockCollection.entries,
      appliedFilters: {
        ...mockCollection.appliedFilters,
        lockedOnly,
        rarities,
        types,
        duplicatesOnly,
      },
    };
  }

  const searchParams = new URLSearchParams({
    page: String(pageParam),
    page_size: String(pageSize),
    locked: String(lockedOnly),
    duplicates_only: String(duplicatesOnly),
  });
  for (const rarity of rarities) {
    searchParams.append("rarities", rarity);
  }
  for (const pokemonType of types) {
    searchParams.append("types", pokemonType);
  }

  const response = await fetch(buildApiUrl(`/api/collection?${searchParams.toString()}`), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppCollectionResponse>(response);
}

export async function getMarketPage(pageParam = 1): Promise<MiniAppMarketResponse> {
  if (!canUseLiveBackend()) {
    return getMockMarket();
  }

  const searchParams = new URLSearchParams({
    page: String(pageParam),
  });
  const response = await fetch(buildApiUrl(`/api/market?${searchParams.toString()}`), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppMarketResponse>(response);
}

export async function getMyMarketListings(): Promise<MiniAppMyMarketListingsResponse> {
  if (!canUseLiveBackend()) {
    const market = getMockMarket();
    return {
      pokecoinBalance: market.pokecoinBalance,
      entries: market.entries.slice(0, 1),
    };
  }

  const response = await fetch(buildApiUrl("/api/market/my/listings"), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppMyMarketListingsResponse>(response);
}

export async function getMyMarketRequests(): Promise<MiniAppMyMarketRequestsResponse> {
  if (!canUseLiveBackend()) {
    return {
      pokecoinBalance: 880,
      entries: [],
    };
  }

  const response = await fetch(buildApiUrl("/api/market/my/requests"), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppMyMarketRequestsResponse>(response);
}

export async function getMarketDetail(listingId: number): Promise<MiniAppMarketDetail> {
  if (!canUseLiveBackend()) {
    return getMockMarketDetail(listingId);
  }

  const response = await fetch(buildApiUrl(`/api/market/${listingId}`), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppMarketDetail>(response);
}

export async function getMyMarketListingDetail(listingId: number): Promise<MiniAppMarketDetail> {
  if (!canUseLiveBackend()) {
    return getMockMarketDetail(listingId);
  }

  const response = await fetch(buildApiUrl(`/api/market/my/listings/${listingId}`), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppMarketDetail>(response);
}

export async function getMyMarketRequestDetail(requestId: number): Promise<MiniAppMarketRequestDetail> {
  if (!canUseLiveBackend()) {
    return getMockMarketRequestDetail(requestId);
  }

  const response = await fetch(buildApiUrl(`/api/market/my/requests/${requestId}`), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppMarketRequestDetail>(response);
}

export async function getPokemonDetail(userPokemonId: number): Promise<MiniAppPokemonDetail> {
  if (!canUseLiveBackend()) {
    return getMockPokemonDetail(userPokemonId);
  }

  const searchParams = new URLSearchParams({
    user_pokemon_id: String(userPokemonId),
  });
  const response = await fetch(buildApiUrl(`/api/pokemon?${searchParams.toString()}`), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppPokemonDetail>(response);
}

export async function getPokemonInstances(
  userPokemonId: number,
): Promise<MiniAppPokemonInstancesResponse> {
  if (!canUseLiveBackend()) {
    const detail = getMockPokemonDetail(userPokemonId);
    return {
      entries: [
        {
          userPokemonId,
          pokemonId: detail.id,
          dexFormCode: detail.dexFormCode,
          name: detail.name,
          rarity: detail.rarity,
          type: detail.type,
          formBadge: detail.formBadge,
          isLocked: detail.isLocked,
          isInPvpTeam: detail.isInPvpTeam,
        },
      ],
    };
  }

  const response = await fetch(buildApiUrl(`/api/pokemon/${userPokemonId}/instances`), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppPokemonInstancesResponse>(response);
}

export async function togglePokemonLock(userPokemonId: number): Promise<MiniAppPokemonDetail> {
  if (!canUseLiveBackend()) {
    const detail = getMockPokemonDetail(userPokemonId);
    return { ...detail, isLocked: !detail.isLocked };
  }

  const response = await fetch(buildApiUrl(`/api/pokemon/${userPokemonId}/lock-toggle`), {
    method: "POST",
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppPokemonDetail>(response);
}

export async function cyclePokemonImage(userPokemonId: number): Promise<MiniAppPokemonDetail> {
  if (!canUseLiveBackend()) {
    return getMockPokemonDetail(userPokemonId);
  }

  const response = await fetch(buildApiUrl(`/api/pokemon/${userPokemonId}/image-cycle`), {
    method: "POST",
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<MiniAppPokemonDetail>(response);
}

export async function releasePokemon(userPokemonId: number): Promise<{
  userPokemonId: number;
  pokemonId: number;
  name: string;
  rarity: string;
  rewardAmount: number;
}> {
  if (!canUseLiveBackend()) {
    const detail = getMockPokemonDetail(userPokemonId);
    return {
      userPokemonId,
      pokemonId: detail.id,
      name: detail.name,
      rarity: detail.rarity,
      rewardAmount: 25,
    };
  }

  const response = await fetch(buildApiUrl(`/api/pokemon/${userPokemonId}/release`), {
    method: "POST",
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<{
    userPokemonId: number;
    pokemonId: number;
    name: string;
    rarity: string;
    rewardAmount: number;
  }>(response);
}

export async function getPokemonSellPrecheck(userPokemonId: number): Promise<{
  ok: boolean;
  error: string | null;
}> {
  if (!canUseLiveBackend()) {
    return {
      ok: true,
      error: null,
    };
  }

  const response = await fetch(buildApiUrl(`/api/pokemon/${userPokemonId}/sell-precheck`), {
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<{
    ok: boolean;
    error: string | null;
  }>(response);
}

export async function sellPokemon(
  userPokemonId: number,
  price: number,
): Promise<{
  listingId: number;
  userPokemonId: number;
  pokemonId: number;
  price: number;
  sellerLabel: string;
  daysRemaining: number;
}> {
  if (!canUseLiveBackend()) {
    const detail = getMockPokemonDetail(userPokemonId);
    return {
      listingId: 999,
      userPokemonId,
      pokemonId: detail.id,
      price,
      sellerLabel: "termenater",
      daysRemaining: 7,
    };
  }

  const response = await fetch(buildApiUrl(`/api/pokemon/${userPokemonId}/sell`), {
    method: "POST",
    headers: {
      ...getAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ price }),
    cache: "no-store",
  });
  return parseJsonResponse<{
    listingId: number;
    userPokemonId: number;
    pokemonId: number;
    price: number;
    sellerLabel: string;
    daysRemaining: number;
  }>(response);
}

export async function buyMarketListing(
  listingId: number,
): Promise<{
  listingId: number;
  userPokemonId: number;
  pokemonId: number;
  price: number;
}> {
  if (!canUseLiveBackend()) {
    return {
      listingId,
      userPokemonId: 1001,
      pokemonId: 25,
      price: 240,
    };
  }

  const response = await fetch(buildApiUrl(`/api/market/${listingId}/buy`), {
    method: "POST",
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<{
    listingId: number;
    userPokemonId: number;
    pokemonId: number;
    price: number;
  }>(response);
}

export async function removeMarketListing(
  listingId: number,
): Promise<{
  listingId: number;
  userPokemonId: number;
  pokemonId: number;
}> {
  if (!canUseLiveBackend()) {
    return {
      listingId,
      userPokemonId: 1001,
      pokemonId: 25,
    };
  }

  const response = await fetch(buildApiUrl(`/api/market/my/listings/${listingId}/remove`), {
    method: "POST",
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<{
    listingId: number;
    userPokemonId: number;
    pokemonId: number;
  }>(response);
}

export async function cancelMarketRequest(
  requestId: number,
): Promise<{
  requestId: number;
  pokemonId: number;
  reservedAmount: number;
}> {
  if (!canUseLiveBackend()) {
    return {
      requestId,
      pokemonId: 25,
      reservedAmount: 240,
    };
  }

  const response = await fetch(buildApiUrl(`/api/market/my/requests/${requestId}/cancel`), {
    method: "POST",
    headers: getAuthHeaders(),
    cache: "no-store",
  });
  return parseJsonResponse<{
    requestId: number;
    pokemonId: number;
    reservedAmount: number;
  }>(response);
}

export async function getTelegramAuthPreview(): Promise<TelegramAuthPreview> {
  const initData = getTelegramInitData();
  if (!canUseLiveBackend()) {
    const devUser = getDevelopmentTelegramUser();
    return {
      authenticated: false,
      authDate: 0,
      message: `Локальный preview пользователя @${devUser.username ?? "termenater"}`,
      telegramUser: {
        id: devUser.id,
        username: devUser.username,
        first_name: devUser.first_name,
        last_name: devUser.last_name,
      },
      profile: getMockProfile(),
    };
  }

  if (!initData) {
    const profile = await getProfile();
    const devUser = getDevelopmentTelegramUser();
    return {
      authenticated: false,
      authDate: 0,
      message: `Локальный preview пользователя @${devUser.username ?? "termenater"}`,
      telegramUser: {
        id: devUser.id,
        username: devUser.username,
        first_name: devUser.first_name,
        last_name: devUser.last_name,
      },
      profile,
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
