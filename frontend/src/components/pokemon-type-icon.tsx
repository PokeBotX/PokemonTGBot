import Image from "next/image";

type PokemonTypeIconProps = {
  type: string;
  className?: string;
};

type PokemonTypeIconsProps = {
  types: string | string[];
  iconClassName?: string;
  wrapperClassName?: string;
};

const TYPE_ICON_BASE_URL = "/type-icons";

const TYPE_ALIASES: Record<string, string> = {
  normal: "normal",
  normalnyy: "normal",
  obychnyy: "normal",
  огонь: "fire",
  fire: "fire",
  вода: "water",
  water: "water",
  трава: "grass",
  grass: "grass",
  электро: "electric",
  electric: "electric",
  лёд: "ice",
  лед: "ice",
  ice: "ice",
  дракон: "dragon",
  dragon: "dragon",
  тьма: "dark",
  dark: "dark",
  фея: "fairy",
  fairy: "fairy",
  бой: "fighting",
  fighting: "fighting",
  полет: "flying",
  полёт: "flying",
  flying: "flying",
  яд: "poison",
  poison: "poison",
  земля: "ground",
  ground: "ground",
  камень: "rock",
  rock: "rock",
  сталь: "steel",
  steel: "steel",
  психический: "psychic",
  psychic: "psychic",
  призрак: "ghost",
  ghost: "ghost",
  жук: "bug",
  bug: "bug",
};

function resolveTypeSlug(type: string) {
  const normalized = type.trim().toLowerCase();
  return TYPE_ALIASES[normalized] ?? "normal";
}

export function parsePokemonTypes(types: string | string[]) {
  const raw = Array.isArray(types)
    ? types
    : types
        .split(/[\/,|]/)
        .map((part) => part.trim())
        .filter(Boolean);

  return Array.from(new Set(raw)).slice(0, 2);
}

export function PokemonTypeIcon({ type, className }: PokemonTypeIconProps) {
  const slug = resolveTypeSlug(type);

  return (
    <Image
      src={`${TYPE_ICON_BASE_URL}/${slug}.svg`}
      alt={`Стихия: ${type}`}
      className={className ?? "h-5 w-5"}
      width={20}
      height={20}
      loading="lazy"
    />
  );
}

export function PokemonTypeIcons({
  types,
  iconClassName,
  wrapperClassName,
}: PokemonTypeIconsProps) {
  const parsedTypes = parsePokemonTypes(types);

  return (
    <div className={wrapperClassName ?? "flex items-center gap-1.5"}>
      {parsedTypes.map((type) => (
        <PokemonTypeIcon key={type} type={type} className={iconClassName ?? "h-4 w-4"} />
      ))}
    </div>
  );
}
