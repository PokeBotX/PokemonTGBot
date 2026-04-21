import { AppShell } from "@/components/app-shell";
import { PokemonCard } from "@/components/pokemon-card";
import { ProfileCard } from "@/components/profile-card";
import { TelegramUserCard } from "@/components/telegram-user-card";
import { Button } from "@/components/ui/button";

const pokemons = [
  {
    id: 1,
    name: "Pikachu",
    type: "Electric",
    level: 12,
    rarity: "Rare",
  },
  {
    id: 2,
    name: "Bulbasaur",
    type: "Grass",
    level: 8,
    rarity: "Common",
  },
  {
    id: 3,
    name: "Charmander",
    type: "Fire",
    level: 10,
    rarity: "Uncommon",
  },
];

export default function Home() {
  return (
    <AppShell>
      <div>
        <p className="text-sm text-slate-400">Telegram Mini App</p>
        <h1 className="mt-2 text-3xl font-bold">PokéCollect</h1>
        <p className="mt-3 text-slate-300">
          Лови, собирай и прокачивай покемонов прямо в Telegram.
        </p>
      </div>

      <TelegramUserCard />

      <ProfileCard />

      <div className="flex flex-col gap-4">
        {pokemons.map((pokemon) => (
          <PokemonCard
            key={pokemon.id}
            name={pokemon.name}
            type={pokemon.type}
            level={pokemon.level}
            rarity={pokemon.rarity}
          />
        ))}
      </div>

      <Button className="h-14 rounded-2xl bg-yellow-400 font-semibold text-slate-950 hover:bg-yellow-300">
        Открыть коллекцию
      </Button>
    </AppShell>
  );
}
