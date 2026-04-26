import { AppShell } from "@/components/app-shell";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { TopHeader } from "@/components/top-header";

export function generateStaticParams() {
  return Array.from({ length: 6 }, (_, index) => ({
    id: String(index + 101),
  }));
}

export default function ShopPokemonPage() {
  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
    >
      <TopHeader />

      <Card className="rounded-2xl border border-slate-700 bg-slate-900 py-4 text-slate-100 shadow-[0_2px_12px_rgba(0,0,0,0.35)]">
        <CardContent className="space-y-4 px-4">
          <div className="mx-auto h-36 w-36 rounded-3xl bg-slate-700" />

          <div className="space-y-2">
            <p className="text-lg font-semibold">Название покемона</p>
            <div className="flex items-center gap-2">
              <Badge className="rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-200 hover:bg-slate-700">
                Эпический
              </Badge>
              <Badge className="rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-200 hover:bg-slate-700">
                Цена: 760 монет
              </Badge>
            </div>
          </div>

          <div className="rounded-2xl bg-slate-800 p-4 text-sm text-slate-300">
            Описание предложения, гарантия, остаток и другие детали покупки.
          </div>

          <Button className="h-11 w-full rounded-xl bg-slate-700 text-slate-100 hover:bg-slate-600">
            Купить
          </Button>
        </CardContent>
      </Card>

      <Link href="/shop" className="text-sm text-slate-400 underline underline-offset-4">
        Вернуться в магазин
      </Link>
    </AppShell>
  );
}
