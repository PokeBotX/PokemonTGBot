import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { ShopScreen } from "@/components/shop-screen";
import { SectionCard } from "@/components/section-card";
import { TopHeader } from "@/components/top-header";

export default function ShopPage() {
  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
      showScrollToTop
    >
      <TopHeader />
      <Suspense
        fallback={
          <SectionCard>
            <div className="space-y-3">
              <div className="h-6 rounded bg-slate-800" />
              <div className="h-36 rounded bg-slate-800" />
            </div>
          </SectionCard>
        }
      >
        <ShopScreen />
      </Suspense>
    </AppShell>
  );
}
