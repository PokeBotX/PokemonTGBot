import { AppShell } from "@/components/app-shell";
import { PokedexScreen } from "@/components/pokedex-screen";

export default function PokedexPage() {
  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
      showScrollToTop
    >
      <PokedexScreen />
    </AppShell>
  );
}
