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
      <CardContent className="relative flex min-h-[220px] flex-col px-2.5 pb-7 pt-2">
        <PokemonTypeIcons
          types={type}
          iconClassName="h-4 w-4"
          wrapperClassName="absolute left-2 top-2 z-10 flex items-center gap-1 rounded-full border border-slate-200/10 bg-slate-950/55 px-2 py-1 shadow-[0_6px_16px_rgba(15,23,42,0.28)] backdrop-blur-md"
        />

        <div className="mt-4 flex flex-1 items-center justify-center overflow-hidden rounded-[1.35rem]">
          {imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imageUrl}
              alt={displayName}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="h-full w-full bg-slate-700" />
          )}
        </div>

        <div className="mt-3 space-y-1.5">
          <CardTitle className="line-clamp-2 text-sm font-medium leading-tight">
            {displayName}
          </CardTitle>

          <div className="flex min-h-[1.5rem] items-center gap-2">
            <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-400">
              #{displayId}
            </p>
            {formBadge ? (
              <PokemonFormBadge formBadge={formBadge} className="text-[10px]" />
            ) : null}
          </div>

          {priceLabel ? (
            <p className="text-right text-xs font-semibold text-amber-300">{priceLabel}</p>
          ) : null}
        </div>
      </CardContent>

      <div
        className={`absolute bottom-0 left-0 z-0 rounded-tr-md rounded-br-md border border-l-0 border-b-0 px-2 py-0.5 text-[10px] font-semibold tracking-[0.12em] ${getRarityTagClass(rarity)}`}
      >
        {getRarityLabel(rarity)}
      </div>
    </Card>
  );
}
