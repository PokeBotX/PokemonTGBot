import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { formatPokemonDisplayId, formatPokemonDisplayName } from "@/lib/pokemon-display";
import { PokemonTypeIcons } from "@/components/pokemon-type-icon";
import { PokemonFormBadge } from "@/components/pokemon-form-badge";
import {
  getRarityBorderClass,
  getRarityLabel,
  getRarityTagClass,
  type PokemonRarity,
} from "@/components/pokemon-rarity";

type PokemonCardProps = {
  pokemonId: number;
  dexFormCode?: string | null;
  name: string;
  type: string;
  rarity: PokemonRarity;
  formBadge?: string | null;
  imageUrl?: string | null;
  priceLabel?: string | null;
};

export function PokemonCard({
  pokemonId,
  dexFormCode,
  name,
  type,
  rarity,
  formBadge,
  imageUrl,
  priceLabel,
}: PokemonCardProps) {
  const displayName = formatPokemonDisplayName(name, formBadge);
  const displayId = formatPokemonDisplayId(pokemonId, dexFormCode);

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
            alt={displayName}
            className="mx-auto mb-3 mt-2 h-28 w-28 rounded-2xl object-cover"
            loading="lazy"
          />
        ) : (
          <div className="mx-auto mb-3 mt-2 h-28 w-28 rounded-2xl bg-slate-700" />
        )}

        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="text-sm font-medium leading-snug">{displayName}</CardTitle>
            <div className="mt-2">
              <PokemonFormBadge formBadge={formBadge} className="text-[10px]" />
            </div>
          </div>
        </div>
        <p className="mt-2 text-xs font-medium uppercase tracking-[0.14em] text-slate-400">
          #{displayId}
        </p>
        {priceLabel ? (
          <p className="mt-3 text-right text-xs font-semibold text-amber-300">{priceLabel}</p>
        ) : null}
      </CardContent>

      <div
        className={`absolute bottom-0 left-0 z-0 rounded-tr-md rounded-br-md border border-l-0 border-b-0 px-2 py-0.5 text-[10px] font-semibold tracking-[0.12em] ${getRarityTagClass(rarity)}`}
      >
        {getRarityLabel(rarity)}
      </div>
    </Card>
  );
}
