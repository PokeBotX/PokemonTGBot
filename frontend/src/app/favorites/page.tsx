import { AppShell } from "@/components/app-shell";
import { PokemonList } from "@/components/pokemon-list";
import { TopHeader } from "@/components/top-header";

export default function FavoritesPage() {
  return (
    <AppShell
      className="bg-slate-950 px-3 py-4 pb-28 text-slate-100"
      navVariant="minimal"
    >
      <TopHeader />
      <PokemonList lockedOnly />
    </AppShell>
  );
}
