"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { MarketList } from "@/components/market-list";
import { PokemonCard } from "@/components/pokemon-card";
import { SectionCard } from "@/components/section-card";
import { Button } from "@/components/ui/button";
import { useMarket } from "@/hooks/use-market";
import { useMyMarketListings, useMyMarketRequests } from "@/hooks/use-shop-market";
import { normalizePokemonRarity } from "@/components/pokemon-rarity";
import { cn } from "@/lib/utils";

type ShopTab = "market" | "listings" | "requests";

const SHOP_TABS: Array<{ key: ShopTab; label: string }> = [
  { key: "market", label: "Магазин" },
  { key: "listings", label: "Мои лоты" },
  { key: "requests", label: "Мои заявки" },
];

function isShopTab(value: string | null): value is ShopTab {
  return value === "market" || value === "listings" || value === "requests";
}

function ShopSubnav({ activeTab, onTabChange }: { activeTab: ShopTab; onTabChange: (tab: ShopTab) => void }) {
  return (
    <nav className="fixed bottom-[78px] left-0 right-0 z-20 px-3">
      <div className="mx-auto flex max-w-md items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900/95 p-2 shadow-[0_18px_40px_rgba(2,6,23,0.45)] backdrop-blur">
        {SHOP_TABS.map((tab) => (
          <Button
            key={tab.key}
            type="button"
            variant="secondary"
            className={cn(
              "flex-1 rounded-xl text-xs",
              activeTab === tab.key
                ? "bg-cyan-300 text-slate-950 hover:bg-cyan-200"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white",
            )}
            onClick={() => onTabChange(tab.key)}
          >
            {tab.label}
          </Button>
        ))}
      </div>
    </nav>
  );
}

export function ShopScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const activeTab: ShopTab = isShopTab(tabParam) ? tabParam : "market";

  const marketQuery = useMarket();
  const listingsQuery = useMyMarketListings();
  const requestsQuery = useMyMarketRequests();

  const balance =
    activeTab === "market"
      ? marketQuery.pokecoinBalance
      : activeTab === "listings"
        ? listingsQuery.data?.pokecoinBalance ?? 0
        : requestsQuery.data?.pokecoinBalance ?? 0;

  const handleTabChange = (tab: ShopTab) => {
    const next = new URLSearchParams(searchParams.toString());
    if (tab === "market") {
      next.delete("tab");
    } else {
      next.set("tab", tab);
    }
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  };

  return (
    <>
      <SectionCard>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Рынок покемонов</h2>
            <p className="mt-1 text-sm text-slate-400">
              {activeTab === "market"
                ? "Покупай активные лоты других тренеров."
                : activeTab === "listings"
                  ? "Управляй своими выставленными лотами."
                  : "Отслеживай свои заявки на покупку."}
            </p>
          </div>
          <div className="rounded-2xl border border-amber-400/20 bg-amber-400/10 px-3 py-2 text-right">
            <p className="text-[11px] uppercase tracking-[0.18em] text-amber-200/70">Pokecoin</p>
            <p className="text-base font-semibold text-amber-200">🪙 {balance}</p>
          </div>
        </div>
      </SectionCard>

      {activeTab === "market" ? (
        <MarketList />
      ) : null}

      {activeTab === "listings" ? (
        listingsQuery.isLoading ? (
          <SectionCard>
            <div className="space-y-3">
              <div className="h-6 rounded bg-slate-800" />
              <div className="h-36 rounded bg-slate-800" />
            </div>
          </SectionCard>
        ) : listingsQuery.isError ? (
          <ErrorState
            icon="🧾"
            title="Не удалось загрузить ваши лоты"
            description="Попробуй открыть раздел ещё раз чуть позже."
          />
        ) : listingsQuery.data && listingsQuery.data.entries.length > 0 ? (
          <div className="grid grid-cols-2 gap-4">
            {listingsQuery.data.entries.map((entry) => (
              <Link key={entry.listingId} href={`/shop/listing?id=${entry.listingId}`} className="block">
                <PokemonCard
                  pokemonId={entry.pokemonId}
                  dexFormCode={entry.dexFormCode}
                  name={entry.name}
                  type={entry.type}
                  rarity={normalizePokemonRarity(entry.rarity)}
                  formBadge={entry.formBadge}
                  imageUrl={entry.imageUrl}
                  priceLabel={`🪙 ${entry.price}`}
                />
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            icon="🧾"
            title="У вас пока нет активных лотов"
            description="Когда выставите покемона на продажу, он появится здесь."
          />
        )
      ) : null}

      {activeTab === "requests" ? (
        requestsQuery.isLoading ? (
          <SectionCard>
            <div className="space-y-3">
              <div className="h-6 rounded bg-slate-800" />
              <div className="h-28 rounded bg-slate-800" />
            </div>
          </SectionCard>
        ) : requestsQuery.isError ? (
          <ErrorState
            icon="📨"
            title="Не удалось загрузить ваши заявки"
            description="Попробуй открыть раздел ещё раз чуть позже."
          />
        ) : requestsQuery.data && requestsQuery.data.entries.length > 0 ? (
          <div className="space-y-3">
            {requestsQuery.data.entries.map((entry) => (
              <SectionCard key={entry.requestId}>
                <div className="flex gap-4">
                  <div className="h-24 w-24 shrink-0 overflow-hidden rounded-2xl bg-slate-800">
                    {entry.imageUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={entry.imageUrl}
                        alt={entry.name}
                        className="h-full w-full object-cover"
                      />
                    ) : null}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-white">
                      {entry.name}
                      {entry.formBadge ? ` (${entry.formBadge.toLowerCase()})` : ""}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-400">
                      #{entry.dexFormCode ?? entry.pokemonId}
                    </p>
                    <p className="mt-2 text-sm text-slate-300">{entry.type}</p>
                    <div className="mt-3 space-y-1 text-sm text-slate-300">
                      <p>Цена: 🪙 {entry.price}</p>
                      <p>Зарезервировано: 🪙 {entry.reservedAmount}</p>
                    </div>
                  </div>
                </div>
              </SectionCard>
            ))}
          </div>
        ) : (
          <EmptyState
            icon="📨"
            title="У вас пока нет активных заявок"
            description="Созданные заявки на покупку появятся здесь."
          />
        )
      ) : null}

      <ShopSubnav activeTab={activeTab} onTabChange={handleTabChange} />
    </>
  );
}
