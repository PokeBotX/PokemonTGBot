import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { PokemonTypeIcons } from "@/components/pokemon-type-icon";
import {
  getRarityBorderClass,
  getRarityLabel,
  getRarityTagClass,
  type PokemonRarity,
} from "@/components/pokemon-rarity";

type PokemonCardProps = {
  pokemonId: number;
  name: string;
  type: string;
  rarity: PokemonRarity;
  imageUrl?: string | null;
  priceLabel?: string | null;
};

export function PokemonCard({
  pokemonId,
  name,
  type,
  rarity,
  imageUrl,
  priceLabel,
}: PokemonCardProps) {
  return (
    <Card
      className={`relative overflow-hidden rounded-2xl border bg-slate-900 py-3 text-slate-100 shadow-[0_2px_12px_rgba(0,0,0,0.35)] ${getRarityBorderClass(rarity)}`}
    >
      <CardContent className="relative px-3 pb-7">
        <PokemonTypeIcons
          types={type}
          iconClassName="h-4 w-4"
          wrapperClassName="absolute left-2 top-1 flex items-center gap-1"
        />

        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={name}
            className="mx-auto mb-3 mt-2 h-24 w-24 rounded-2xl object-cover"
            loading="lazy"
          />
        ) : (
          <div className="mx-auto mb-3 mt-2 h-24 w-24 rounded-2xl bg-slate-700" />
        )}

        <CardTitle className="text-sm font-medium leading-snug">{name}</CardTitle>
        <p className="mt-2 text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
          #{pokemonId}
        </p>
        {priceLabel ? (
          <p className="mt-3 text-right text-xs font-semibold text-amber-300">{priceLabel}</p>
        ) : null}
      </CardContent>

      <div
        className={`absolute bottom-0 left-0 z-10 rounded-tr-md rounded-br-md border border-l-0 border-b-0 px-2 py-0.5 text-[10px] font-semibold tracking-[0.12em] ${getRarityTagClass(rarity)}`}
      >
        {getRarityLabel(rarity)}
      </div>
    </Card>
  );
}
