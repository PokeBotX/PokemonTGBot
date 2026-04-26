import { AppShell } from "@/components/app-shell";
import { MarketList } from "@/components/market-list";
import { TopHeader } from "@/components/top-header";

export default function ShopPage() {
  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
    >
      <TopHeader />
      <MarketList />
    </AppShell>
  );
}
