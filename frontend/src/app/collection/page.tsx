import { AppShell } from "@/components/app-shell";
import { PokemonList } from "@/components/pokemon-list";

export default function CollectionPage() {
  return (
    <AppShell>
      <div>
        <p className="text-sm text-slate-400">Коллекция</p>
        <h1 className="mt-2 text-3xl font-bold">Мои покемоны</h1>
        <p className="mt-3 text-slate-300">
          Здесь будет твоя коллекция, редкость, уровни и карточки.
        </p>
      </div>

      <PokemonList />
    </AppShell>
  );
}
