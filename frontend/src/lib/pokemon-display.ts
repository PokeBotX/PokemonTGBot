export function formatPokemonDisplayName(name: string, formBadge?: string | null): string {
  const normalizedName = name.trim();
  if (!formBadge) {
    return normalizedName;
  }
  return `${normalizedName} (${formBadge.toLowerCase()})`;
}

export function formatPokemonDisplayId(pokemonId: number, dexFormCode?: string | null): string {
  const normalizedFormCode = dexFormCode?.trim();
  if (normalizedFormCode) {
    return normalizedFormCode.split("-", 1)[0] ?? normalizedFormCode;
  }
  return String(pokemonId);
}
