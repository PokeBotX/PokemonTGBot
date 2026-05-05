export type PokemonRarity = "legendary" | "epic" | "rare" | "common";

export function normalizePokemonRarity(rarity: string): PokemonRarity {
  const normalized = rarity.trim().toLowerCase();

  switch (normalized) {
    case "legendary":
    case "легендарный":
      return "legendary";
    case "epic":
    case "эпический":
      return "epic";
    case "rare":
    case "редкий":
      return "rare";
    case "common":
    case "обычный":
    default:
      return "common";
  }
}

export function getRarityBorderClass(rarity: PokemonRarity) {
  switch (rarity) {
    case "legendary":
      return "border-amber-700/70";
    case "epic":
      return "border-violet-500/90";
    case "rare":
      return "border-emerald-700/65";
    case "common":
    default:
      return "border-stone-500/70";
  }
}

export function getRarityTagClass(rarity: PokemonRarity) {
  switch (rarity) {
    case "legendary":
      return "border-amber-700/70 bg-slate-950 text-amber-300";
    case "epic":
      return "border-violet-400/85 bg-slate-950 text-violet-200";
    case "rare":
      return "border-emerald-700/65 bg-slate-950 text-emerald-300";
    case "common":
    default:
      return "border-stone-500/70 bg-slate-950 text-stone-300";
  }
}

export function getRarityLabel(rarity: PokemonRarity) {
  return rarity.toUpperCase();
}
