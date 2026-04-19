type PokemonCardProps = {
  name: string;
  type: string;
  level: number;
  rarity: string;
};

export function PokemonCard({ name, type, level, rarity }: PokemonCardProps) {
  return (
    <div className="rounded-3xl border border-slate-800 bg-slate-900 p-5 shadow-lg">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm text-slate-400">{type}</p>
          <h3 className="mt-1 text-xl font-bold">{name}</h3>
        </div>

        <span className="rounded-full bg-yellow-400 px-3 py-1 text-xs font-bold text-slate-950">
          Lv. {level}
        </span>
      </div>

      <div className="mt-4 rounded-2xl bg-slate-800 p-4 text-center text-5xl">
        ⚡
      </div>

      <p className="mt-4 text-sm text-slate-300">Редкость: {rarity}</p>
    </div>
  );
}
