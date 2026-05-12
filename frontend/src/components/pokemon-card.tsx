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
  stateBadgeLabel?: string | null;
  dimmed?: boolean;
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
  stateBadgeLabel,
  dimmed = false,
}: PokemonCardProps) {
  const displayName = formatPokemonDisplayName(name, formBadge);
  const displayId = formatPokemonDisplayId(pokemonId, dexFormCode);

  return (
    <Card
      className={`relative h-[220px] gap-0 overflow-hidden rounded-2xl border bg-slate-900 py-0 text-slate-100 shadow-[0_2px_12px_rgba(0,0,0,0.35)] ${getRarityBorderClass(rarity)} ${dimmed ? "opacity-70 saturate-50" : ""}`}
    >
      <CardContent className="relative h-full overflow-hidden p-0">
        <div className="absolute inset-0">
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

        <PokemonTypeIcons
          types={type}
          iconClassName="h-4 w-4"
          wrapperClassName="absolute left-2 top-2 z-10 flex items-center gap-1 rounded-full border border-slate-200/5 bg-slate-950/30 px-2 py-1 shadow-[0_8px_24px_rgba(15,23,42,0.18)] backdrop-blur-xl"
        />

        {stateBadgeLabel ? (
          <div className="absolute right-2 top-2 z-10 rounded-full border border-slate-200/5 bg-slate-950/65 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-100 shadow-[0_8px_24px_rgba(15,23,42,0.18)] backdrop-blur-xl">
            {stateBadgeLabel}
          </div>
        ) : null}

        <div className="absolute inset-x-0 bottom-0 z-10 flex min-h-[96px] flex-col justify-end bg-gradient-to-t from-slate-950 via-slate-950/72 via-35% to-transparent px-3 pb-8 pt-20">
          <CardTitle className="line-clamp-1 text-sm font-medium leading-tight">
            {displayName}
          </CardTitle>

          <div className="mt-2 flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-400">
                #{displayId}
              </p>
              {formBadge ? (
                <PokemonFormBadge formBadge={formBadge} className="text-[10px]" />
              ) : null}
            </div>

            {priceLabel ? (
              <p className="shrink-0 text-xs font-semibold text-amber-300">{priceLabel}</p>
            ) : null}
          </div>
        </div>
      </CardContent>

      <div
        className={`absolute bottom-0 left-0 z-20 rounded-tr-md rounded-br-md border border-l-0 border-b-0 px-2 py-0.5 text-[10px] font-semibold tracking-[0.12em] ${getRarityTagClass(rarity)}`}
      >
        {getRarityLabel(rarity)}
      </div>
    </Card>
  );
}
