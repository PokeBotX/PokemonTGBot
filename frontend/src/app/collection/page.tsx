import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { PokemonList } from "@/components/pokemon-list";

export default function CollectionPage() {
  return (
    <AppShell>
      <PageHeader
        eyebrow="Коллекция"
        title="Мои покемоны"
        description="Здесь будет твоя коллекция, редкость, уровни и карточки."
      />

      <PokemonList />
    </AppShell>
  );
}
