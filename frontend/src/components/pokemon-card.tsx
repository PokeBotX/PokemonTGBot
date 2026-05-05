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
      className={`relative overflow-hidden rounded-2xl border bg-slate-900 py-2 text-slate-100 shadow-[0_2px_12px_rgba(0,0,0,0.35)] ${getRarityBorderClass(rarity)}`}
    >
      <CardContent className="relative flex min-h-[220px] flex-col px-2.5 pb-3 pt-2">
        <PokemonTypeIcons
          types={type}
          iconClassName="h-4 w-4"
          wrapperClassName="absolute left-2 top-2 z-10 flex items-center gap-1 rounded-full border border-slate-200/10 bg-slate-950/60 px-2 py-1 shadow-[0_8px_20px_rgba(15,23,42,0.28)] backdrop-blur-md"
        />

        <div
          className={`absolute right-2 top-2 z-10 rounded-full border px-2 py-1 text-[10px] font-semibold tracking-[0.12em] shadow-[0_8px_20px_rgba(15,23,42,0.28)] backdrop-blur-md ${getRarityTagClass(rarity)}`}
        >
          {getRarityLabel(rarity)}
        </div>

        {imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={displayName}
            className="mx-auto mb-2 mt-7 h-32 w-32 rounded-[1.35rem] object-cover"
            loading="lazy"
          />
        ) : (
          <div className="mx-auto mb-2 mt-7 h-32 w-32 rounded-[1.35rem] bg-slate-700" />
        )}

        <div className="mt-auto space-y-2">
          <CardTitle className="line-clamp-2 text-sm font-semibold leading-tight">
            {displayName}
          </CardTitle>

          <div className="flex min-h-[1.5rem] items-center gap-2">
            <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-slate-400">
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
    </Card>
  );
}
